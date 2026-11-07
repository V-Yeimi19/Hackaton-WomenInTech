"""Compromisos de pago próximos y faltantes por medio."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.audit.service import record as audit_record
from app.modules.commitments.models import Commitment
from app.modules.commitments.schemas import CommitmentCreate
from app.modules.ledger import domain as ledger_domain
from app.modules.ledger import service as ledger_service
from app.modules.ledger.models import Account
from app.shared.money import Money, money_str

ZERO = Decimal("0.00")
ACCOUNT_FOR_MEDIUM = {
    ledger_domain.DIGITAL: ledger_domain.BUSINESS_DIGITAL,
    ledger_domain.CASH: ledger_domain.CASH_DECLARED,
}
MEDIUM_FOR_ACCOUNT = {
    ledger_domain.BUSINESS_DIGITAL: ledger_domain.DIGITAL,
    ledger_domain.CASH_DECLARED: ledger_domain.CASH,
}


def _account_for_medium(db: Session, business_id: uuid.UUID, medium: str) -> Account:
    kind = ACCOUNT_FOR_MEDIUM.get(medium)
    if kind is None:
        raise AppError("INVALID_MEDIUM", "Medio de pago inválido.", 422)
    return ledger_service.get_account(db, business_id, kind)


def create(db: Session, business_id: uuid.UUID, payload: CommitmentCreate) -> Commitment:
    money = Money.parse(payload.amount, payload.currency)

    if payload.payment_account_id is not None:
        account = db.get(Account, payload.payment_account_id)
        if account is None or account.business_id != business_id:
            raise AppError("NOT_FOUND", "Cuenta de pago no encontrada.", 404)
        if account.kind not in (ledger_domain.BUSINESS_DIGITAL, ledger_domain.CASH_DECLARED):
            raise AppError("INVALID_ACCOUNT", "La cuenta no es un medio de pago válido.", 422)
    else:
        account = _account_for_medium(db, business_id, payload.medium)

    commitment = Commitment(
        business_id=business_id,
        label=payload.label.strip(),
        amount=money.amount,
        payment_account_id=account.id,
        due_at=payload.due_at,
        source="USER_DECLARED",
        confirmed_at=utcnow() if payload.confirmed else None,
        status="OPEN",
    )
    db.add(commitment)
    db.flush()
    audit_record(
        db,
        business_id,
        "COMMITMENT_CREATED",
        "commitment",
        commitment.id,
        metadata={
            "amount": money_str(money.amount),
            "due_at": payload.due_at.isoformat(),
            "account_kind": account.kind,
        },
    )
    db.commit()
    db.refresh(commitment)
    return commitment


def list_commitments(
    db: Session,
    business_id: uuid.UUID,
    *,
    status: str | None = None,
) -> list[Commitment]:
    stmt = select(Commitment).where(Commitment.business_id == business_id)
    if status:
        stmt = stmt.where(Commitment.status == status)
    return list(db.scalars(stmt.order_by(Commitment.due_at.asc())))


def get(db: Session, business_id: uuid.UUID, commitment_id: uuid.UUID) -> Commitment:
    commitment = db.scalar(
        select(Commitment).where(Commitment.id == commitment_id).with_for_update()
    )
    if commitment is None or commitment.business_id != business_id:
        raise AppError("NOT_FOUND", "Compromiso no encontrado.", 404)
    return commitment


def mark_paid(db: Session, commitment: Commitment, transaction_id: uuid.UUID) -> Commitment:
    if commitment.status == "PAID":
        return commitment
    commitment.status = "PAID"
    commitment.paid_transaction_id = transaction_id
    db.flush()
    return commitment


def upcoming_shortfall(
    db: Session,
    business_id: uuid.UUID,
    *,
    now: datetime | None = None,
    days: int = 7,
) -> dict[str, Decimal]:
    """Devuelve el faltante por medio para compromisos de los próximos 7 días.

    Solo considera compromisos explícitos y confirmados. No descuenta efectivo
    de un pago digital ni viceversa.
    """
    now = now or utcnow()
    horizon = now + timedelta(days=days)
    commitments = list(
        db.scalars(
            select(Commitment).where(
                Commitment.business_id == business_id,
                Commitment.status == "OPEN",
                Commitment.confirmed_at.is_not(None),
                Commitment.due_at >= now,
                Commitment.due_at <= horizon,
            )
        )
    )
    if not commitments:
        return {}

    accounts = {
        account.id: account
        for account in db.scalars(select(Account).where(Account.business_id == business_id))
    }
    required: dict[str, Decimal] = {}
    for commitment in commitments:
        account = accounts.get(commitment.payment_account_id)
        medium = MEDIUM_FOR_ACCOUNT.get(account.kind if account else "")
        if medium is None:
            continue
        required[medium] = required.get(medium, ZERO) + commitment.amount

    balances = ledger_service.balances(db, business_id)
    available = {
        ledger_domain.DIGITAL: Decimal(balances["business_digital"]),
        ledger_domain.CASH: Decimal(balances["cash_declared"]),
    }

    shortfall: dict[str, Decimal] = {}
    for medium, amount in required.items():
        missing = amount - available.get(medium, ZERO)
        if missing > 0:
            shortfall[medium] = missing.quantize(Decimal("0.01"))
    return shortfall


def shortfall_details(
    db: Session,
    business_id: uuid.UUID,
    *,
    now: datetime | None = None,
    days: int = 7,
) -> list[dict]:
    """Detalle legible para la alerta: fecha, importe y faltante por compromiso."""
    now = now or utcnow()
    horizon = now + timedelta(days=days)
    commitments = list(
        db.scalars(
            select(Commitment)
            .where(
                Commitment.business_id == business_id,
                Commitment.status == "OPEN",
                Commitment.confirmed_at.is_not(None),
                Commitment.due_at >= now,
                Commitment.due_at <= horizon,
            )
            .order_by(Commitment.due_at.asc())
        )
    )
    accounts = {
        account.id: account
        for account in db.scalars(select(Account).where(Account.business_id == business_id))
    }
    balances = ledger_service.balances(db, business_id)
    available = {
        ledger_domain.DIGITAL: Decimal(balances["business_digital"]),
        ledger_domain.CASH: Decimal(balances["cash_declared"]),
    }
    details: list[dict] = []
    for commitment in commitments:
        account = accounts.get(commitment.payment_account_id)
        medium = MEDIUM_FOR_ACCOUNT.get(account.kind if account else "")
        if medium is None:
            continue
        missing = max(commitment.amount - available.get(medium, ZERO), ZERO)
        if missing > 0:
            details.append(
                {
                    "commitment_id": str(commitment.id),
                    "label": commitment.label,
                    "due_at": commitment.due_at.isoformat(),
                    "amount": money_str(commitment.amount),
                    "medium": medium,
                    "shortfall": money_str(missing),
                }
            )
    return details
