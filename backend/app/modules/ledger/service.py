"""Servicio del libro financiero.

Reglas clave:
- Todo importe usa Decimal/NUMERIC(14,2).
- Cada operación confirmada publica asientos que suman cero.
- Los saldos se calculan siempre desde asientos, nunca desde una fórmula de ventas.
- Una operación iniciada por la usuaria no puede dejar saldo negativo en una
  cuenta visible; se bloquean las cuentas con SELECT FOR UPDATE.
- Las operaciones confirmadas no se editan: se revierten con una compensación.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.audit.service import record as audit_record
from app.modules.ledger import domain
from app.modules.ledger.models import Account, IdempotencyRecord, LedgerEntry, Transaction
from app.shared.clock import parse_datetime
from app.shared.money import money_str

ZERO = Decimal("0.00")


def ensure_accounts(db: Session, business_id: uuid.UUID) -> dict[str, Account]:
    existing = {
        account.kind: account
        for account in db.scalars(select(Account).where(Account.business_id == business_id))
    }
    for kind in domain.ACCOUNT_KINDS:
        if kind not in existing:
            account = Account(business_id=business_id, kind=kind, currency="PEN")
            db.add(account)
            existing[kind] = account
    db.flush()
    return existing


def get_account(
    db: Session, business_id: uuid.UUID, kind: str, *, for_update: bool = False
) -> Account:
    stmt = select(Account).where(
        Account.business_id == business_id,
        Account.kind == kind,
    )
    if for_update:
        stmt = stmt.with_for_update()
    account = db.scalar(stmt)
    if account is None:
        raise AppError("ACCOUNT_NOT_FOUND", "Cuenta contable no encontrada.", 500, {"kind": kind})
    return account


def account_balance(db: Session, account_id: uuid.UUID) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.delta), 0)).where(
            LedgerEntry.account_id == account_id
        )
    )
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def balances(db: Session, business_id: uuid.UUID) -> dict[str, str]:
    rows = db.execute(
        select(Account.kind, func.coalesce(func.sum(LedgerEntry.delta), 0))
        .outerjoin(LedgerEntry, LedgerEntry.account_id == Account.id)
        .where(Account.business_id == business_id)
        .group_by(Account.kind)
    ).all()
    raw = {kind: Decimal(str(total or 0)).quantize(Decimal("0.01")) for kind, total in rows}
    return {
        "business_digital": money_str(raw.get(domain.BUSINESS_DIGITAL, ZERO)),
        "household_digital": money_str(raw.get(domain.HOUSEHOLD_DIGITAL, ZERO)),
        "cash_declared": money_str(raw.get(domain.CASH_DECLARED, ZERO)),
    }


def last_updated(db: Session, business_id: uuid.UUID) -> datetime:
    value = db.scalar(
        select(func.max(LedgerEntry.created_at)).where(LedgerEntry.business_id == business_id)
    )
    return value or utcnow()


def find_by_external(
    db: Session,
    provider: str | None,
    environment: str,
    external_transaction_id: str | None,
) -> Transaction | None:
    if not provider or not external_transaction_id:
        return None
    return db.scalar(
        select(Transaction).where(
            Transaction.provider == provider,
            Transaction.environment == environment,
            Transaction.external_transaction_id == external_transaction_id,
        )
    )


def _lock_display_accounts(db: Session, business_id: uuid.UUID) -> dict[str, Account]:
    locked: dict[str, Account] = {}
    for kind in sorted(domain.DISPLAY_ACCOUNTS):
        locked[kind] = get_account(db, business_id, kind, for_update=True)
    return locked


def _check_non_negative(
    db: Session, locked: dict[str, Account], drafts: list[domain.EntryDraft]
) -> None:
    for draft in drafts:
        if draft.delta >= 0 or not domain.is_debit_account(draft.account_kind):
            continue
        account = locked[draft.account_kind]
        current = account_balance(db, account.id)
        if current + draft.delta < 0:
            raise AppError(
                "INSUFFICIENT_BALANCE",
                "Saldo insuficiente en el bolsillo de origen.",
                409,
                {
                    "account": draft.account_kind,
                    "available": money_str(current),
                    "required": money_str(-draft.delta),
                },
            )


def post(
    db: Session,
    *,
    business_id: uuid.UUID,
    kind: str,
    amount: Decimal,
    medium: str = domain.DIGITAL,
    source: str,
    environment: str = "DEMO",
    classification_source: str = domain.EXPLICIT_ACTION,
    occurred_at: datetime,
    provider: str | None = None,
    external_transaction_id: str | None = None,
    inbound_event_id: uuid.UUID | None = None,
    description: str | None = None,
    target_account_kind: str | None = None,
    actor_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Transaction:
    if source == domain.PROVIDER_CONFIRMED and environment == "DEMO":
        raise AppError(
            "INVALID_SOURCE",
            "PROVIDER_CONFIRMED no está permitido en DEMO.",
            422,
        )

    existing = find_by_external(db, provider, environment, external_transaction_id)
    if existing is not None:
        if (
            existing.business_id != business_id
            or existing.amount != amount
            or existing.kind != kind
        ):
            raise AppError(
                "EXTERNAL_TRANSACTION_CONFLICT", "Identificador externo en conflicto.", 409
            )
        return existing

    drafts = domain.entries_for(kind, amount, medium, target_account_kind)
    ensure_accounts(db, business_id)
    locked = _lock_display_accounts(db, business_id)
    existing = find_by_external(db, provider, environment, external_transaction_id)
    if existing is not None:
        if (
            existing.business_id != business_id
            or existing.amount != amount
            or existing.kind != kind
        ):
            raise AppError(
                "EXTERNAL_TRANSACTION_CONFLICT", "Identificador externo en conflicto.", 409
            )
        return existing
    _check_non_negative(db, locked, drafts)

    transaction = Transaction(
        business_id=business_id,
        kind=kind,
        amount=amount,
        medium=medium,
        currency="PEN",
        status="POSTED",
        source=source,
        environment=environment,
        classification_source=classification_source,
        occurred_at=occurred_at,
        confirmed_at=utcnow(),
        provider=provider,
        external_transaction_id=external_transaction_id,
        inbound_event_id=inbound_event_id,
        description=description,
    )
    db.add(transaction)
    db.flush()

    for draft in drafts:
        account = locked.get(draft.account_kind) or get_account(db, business_id, draft.account_kind)
        db.add(
            LedgerEntry(
                business_id=business_id,
                transaction_id=transaction.id,
                account_id=account.id,
                delta=draft.delta,
            )
        )
    db.flush()

    audit_record(
        db,
        business_id,
        "TRANSACTION_POSTED",
        "transaction",
        transaction.id,
        actor_id=actor_id,
        metadata={"kind": kind, "amount": money_str(amount), "medium": medium},
    )
    schedule_report_revisions(db, business_id, occurred_at)
    if commit:
        db.commit()
        db.refresh(transaction)
    return transaction


def post_reversal(
    db: Session,
    original: Transaction,
    *,
    reason: str,
    actor_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Transaction:
    original = db.scalars(
        select(Transaction).where(Transaction.id == original.id).with_for_update()
    ).one()
    existing = db.scalar(select(Transaction).where(Transaction.reversal_of == original.id))
    if existing is not None:
        return existing

    # Una reclasificación a retiro agrega un ajuste ligado a la operación
    # original. La reversión debe invertir también ese ajuste en una sola
    # transacción para no dejar el hogar con dinero inexistente.
    adjustment_ids = list(
        db.scalars(select(Transaction.id).where(Transaction.adjustment_of == original.id))
    )
    transaction_ids = [original.id, *adjustment_ids]
    entries = db.execute(
        select(LedgerEntry.account_id, LedgerEntry.delta).where(
            LedgerEntry.transaction_id.in_(transaction_ids)
        )
    ).all()
    if not entries:
        raise AppError("REVERSAL_WITHOUT_ENTRIES", "La operación no tiene asientos.", 500)

    _lock_display_accounts(db, original.business_id)

    reversal = Transaction(
        business_id=original.business_id,
        kind=domain.REVERSAL,
        amount=original.amount,
        medium=original.medium,
        currency=original.currency,
        status="POSTED",
        source=domain.USER_DECLARED,
        environment=original.environment,
        classification_source=domain.USER_CONFIRMED,
        occurred_at=utcnow(),
        confirmed_at=utcnow(),
        reversal_of=original.id,
        description=reason,
    )
    db.add(reversal)
    db.flush()

    for account_id, delta in entries:
        db.add(
            LedgerEntry(
                business_id=original.business_id,
                transaction_id=reversal.id,
                account_id=account_id,
                delta=-delta,
            )
        )
    db.flush()

    audit_record(
        db,
        original.business_id,
        "TRANSACTION_REVERSED",
        "transaction",
        reversal.id,
        actor_id=actor_id,
        reason=reason,
        metadata={"reversal_of": str(original.id)},
    )
    schedule_report_revisions(db, original.business_id, original.occurred_at)
    schedule_report_revisions(db, original.business_id, reversal.occurred_at)
    if commit:
        db.commit()
        db.refresh(reversal)
    return reversal


def post_adjustment(
    db: Session,
    original: Transaction,
    *,
    target_account_kind: str,
    actor_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Transaction:
    drafts = domain.classification_adjustment_entries(original.amount, target_account_kind)
    ensure_accounts(db, original.business_id)
    locked = _lock_display_accounts(db, original.business_id)

    adjustment = Transaction(
        business_id=original.business_id,
        kind=domain.CLASSIFICATION_ADJUSTMENT,
        amount=original.amount,
        medium=original.medium,
        currency=original.currency,
        status="POSTED",
        source=domain.USER_DECLARED,
        environment=original.environment,
        classification_source=domain.USER_CONFIRMED,
        occurred_at=utcnow(),
        confirmed_at=utcnow(),
        adjustment_of=original.id,
        description="Ajuste de clasificación",
    )
    db.add(adjustment)
    db.flush()

    for draft in drafts:
        account = locked.get(draft.account_kind) or get_account(
            db, original.business_id, draft.account_kind
        )
        db.add(
            LedgerEntry(
                business_id=original.business_id,
                transaction_id=adjustment.id,
                account_id=account.id,
                delta=draft.delta,
            )
        )
    db.flush()

    audit_record(
        db,
        original.business_id,
        "CLASSIFICATION_ADJUSTED",
        "transaction",
        adjustment.id,
        actor_id=actor_id,
        metadata={"adjustment_of": str(original.id)},
    )
    if commit:
        db.commit()
        db.refresh(adjustment)
    return adjustment


def transaction_to_dict(transaction: Transaction) -> dict[str, Any]:
    return {
        "id": str(transaction.id),
        "kind": transaction.kind,
        "amount": money_str(transaction.amount),
        "currency": transaction.currency,
        "medium": transaction.medium,
        "status": transaction.status,
        "source": transaction.source,
        "environment": transaction.environment,
        "classification_source": transaction.classification_source,
        "occurred_at": transaction.occurred_at.isoformat(),
        "description": transaction.description,
        "reversal_of": str(transaction.reversal_of) if transaction.reversal_of else None,
        "replacement_for": str(transaction.replacement_for)
        if transaction.replacement_for
        else None,
        "adjustment_of": str(transaction.adjustment_of) if transaction.adjustment_of else None,
    }


def _encode_cursor(transaction: Transaction) -> str:
    raw = f"{transaction.occurred_at.isoformat()}|{transaction.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        occurred, identifier = raw.split("|", 1)
        return parse_datetime(occurred), uuid.UUID(identifier)
    except Exception as exc:
        raise AppError("INVALID_CURSOR", "Cursor inválido.", 400) from exc


def list_transactions(
    db: Session,
    business_id: uuid.UUID,
    *,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[Transaction], str | None]:
    limit = max(1, min(limit, 100))
    stmt = select(Transaction).where(Transaction.business_id == business_id)
    if cursor:
        occurred_at, identifier = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Transaction.occurred_at < occurred_at,
                and_(
                    Transaction.occurred_at == occurred_at,
                    Transaction.id < identifier,
                ),
            )
        )
    stmt = stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt))
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _encode_cursor(rows[-1])
    return rows, next_cursor


def request_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return money_str(value)
    return value


def run_idempotent(
    db: Session,
    *,
    business_id: uuid.UUID,
    route: str,
    key: str | None,
    payload: dict[str, Any],
    fn: Callable[[], tuple[int, dict[str, Any]]],
) -> tuple[int, dict[str, Any]]:
    if not key:
        raise AppError(
            "IDEMPOTENCY_KEY_REQUIRED",
            "Las operaciones de escritura financiera requieren Idempotency-Key.",
            400,
        )

    # Une la reserva de clave y los efectos en la misma transacción, también
    # cuando dos peticiones idénticas llegan antes del primer commit.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"{business_id}:{route}:{key}"},
    )
    digest = request_hash(payload)
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.business_id == business_id,
            IdempotencyRecord.route == route,
            IdempotencyRecord.key == key,
        )
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise AppError(
                "IDEMPOTENCY_CONFLICT",
                "La misma Idempotency-Key se usó con otro cuerpo.",
                409,
            )
        return existing.response_status, existing.response_body

    try:
        status_code, body = fn()
        record = IdempotencyRecord(
            business_id=business_id,
            route=route,
            key=key,
            request_hash=digest,
            response_status=status_code,
            response_body=jsonable(body),
            expires_at=utcnow() + timedelta(days=7),
        )
        db.add(record)
        db.commit()
        return status_code, jsonable(body)
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.business_id == business_id,
                IdempotencyRecord.route == route,
                IdempotencyRecord.key == key,
            )
        )
        if existing is not None and existing.request_hash == digest:
            return existing.response_status, existing.response_body
        raise AppError(
            "IDEMPOTENCY_CONFLICT",
            "Conflicto de idempotencia.",
            409,
        ) from None
    except Exception:
        db.rollback()
        raise


def schedule_report_revisions(db: Session, business_id: uuid.UUID, occurred_at: datetime) -> None:
    """Revisar periodos afectados sin modificar snapshots ni reenviar mensajes."""
    from app.jobs.service import JOB_WEEKLY_REPORT, enqueue
    from app.modules.insights.models import WeeklyReport

    reports = list(
        db.scalars(
            select(WeeklyReport)
            .where(
                WeeklyReport.business_id == business_id,
                WeeklyReport.period_start <= occurred_at,
                WeeklyReport.period_end > occurred_at,
            )
            .order_by(WeeklyReport.generated_at.desc())
        )
    )
    seen = set()
    for report in reports:
        identity = (report.period_start, report.kind)
        if identity in seen:
            continue
        seen.add(identity)
        cutoff = utcnow() if report.kind == "WEEKLY_FINAL" else report.data_cutoff_at
        enqueue(
            db,
            business_id=business_id,
            kind=JOB_WEEKLY_REPORT,
            dedupe_key=f"revision:{report.id}:{uuid.uuid4().hex}",
            payload={
                "period_start": report.period_start.isoformat(),
                "cutoff_at": cutoff.isoformat(),
                "kind": report.kind,
                "revision_only": True,
            },
            commit=False,
        )
