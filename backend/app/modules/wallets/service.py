"""Billeteras, yapeos y transferencias sobre el libro de doble entrada.

Reglas:
- Cada billetera tiene su cuenta: Principal -> HOUSEHOLD_DIGITAL, negocio ->
  BUSINESS_DIGITAL y ahorro/creadas -> WALLET. Así los reportes negocio/hogar
  siguen funcionando sin cambios.
- Toda operación publica asientos balanceados (triggers de la BD) y ninguna
  billetera queda en negativo: se bloquean las cuentas con SELECT FOR UPDATE.
- Eliminar una billetera la archiva: el libro es inmutable, sus movimientos se
  ocultan de las listas pero quedan para auditoría.
- Los yapeos tienen límite por operación y diario, validados en el servidor.
"""

from __future__ import annotations

import hashlib
import random
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.audit.service import record as audit_record
from app.modules.ledger import domain
from app.modules.ledger import service as ledger_service
from app.modules.ledger.models import Account, LedgerEntry, Transaction
from app.modules.wallets.models import (
    PURPOSE_BUSINESS,
    PURPOSE_PERSONAL,
    PURPOSE_SAVINGS,
    ROLE_BUSINESS,
    ROLE_CUSTOM,
    ROLE_PRINCIPAL,
    ROLE_SAVINGS,
    Wallet,
)
from app.shared.clock import business_tz, to_business
from app.shared.money import Money, money_str

settings = get_settings()

ZERO = Decimal("0.00")
YAPE_PROVIDER = "yape"
MAX_CUSTOM_WALLETS = 5
NAME_MIN, NAME_MAX = 3, 24
NOTE_MAX = 40

CATEGORY_LABELS = {
    "RESTOCK": "📦 Para volver a surtir",
    "LOCAL_SERVICES": "💡 Para pagar local/servicios/ayudantes",
    "FAMILY": "👨‍👩‍👧 Para mí o mi familia",
}
# Salidas que cuentan para el límite diario de yapeos.
OUTGOING_YAPE_KINDS = (
    domain.BUSINESS_PAYMENT,
    domain.HOUSEHOLD_WITHDRAWAL,
    domain.UNKNOWN_OUTFLOW,
    domain.PERSONAL_PAYMENT,
)
TRANSFER_KINDS = (domain.WALLET_TRANSFER, domain.HOUSEHOLD_WITHDRAWAL, domain.OWNER_CONTRIBUTION)

# (rol, nombre, propósito, tipo de cuenta, ícono)
DEFAULT_WALLETS = (
    (
        ROLE_PRINCIPAL,
        "Principal",
        PURPOSE_PERSONAL,
        domain.HOUSEHOLD_DIGITAL,
        "account_balance_wallet",
    ),
    (ROLE_BUSINESS, "Emprendimiento Café", PURPOSE_BUSINESS, domain.BUSINESS_DIGITAL, "storefront"),
    (ROLE_SAVINGS, "Ahorro Vacaciones", PURPOSE_SAVINGS, domain.WALLET, "savings"),
)


# --------------------------------------------------------------------------- billeteras


def _new_wallet_account(db: Session, business_id: uuid.UUID) -> Account:
    account = Account(business_id=business_id, kind=domain.WALLET, currency="PEN")
    db.add(account)
    db.flush()
    return account


def ensure_default_wallets(db: Session, business_id: uuid.UUID) -> list[Wallet]:
    """Crea Principal, negocio y ahorro si nunca existieron (una billetera archivada no se recrea)."""
    accounts = ledger_service.ensure_accounts(db, business_id)
    existing_roles = set(db.scalars(select(Wallet.role).where(Wallet.business_id == business_id)))
    for position, (role, name, purpose, kind, icon) in enumerate(DEFAULT_WALLETS):
        if role in existing_roles:
            continue
        account = _new_wallet_account(db, business_id) if kind == domain.WALLET else accounts[kind]
        db.add(
            Wallet(
                business_id=business_id,
                account_id=account.id,
                name=name,
                role=role,
                purpose=purpose,
                icon=icon,
                position=position,
                status="ACTIVE",
            )
        )
    db.flush()
    return active_wallets(db, business_id)


def active_wallets(db: Session, business_id: uuid.UUID) -> list[Wallet]:
    return list(
        db.scalars(
            select(Wallet)
            .where(Wallet.business_id == business_id, Wallet.status == "ACTIVE")
            .order_by(Wallet.position, Wallet.created_at)
        )
    )


def all_wallets(db: Session, business_id: uuid.UUID) -> list[Wallet]:
    return list(db.scalars(select(Wallet).where(Wallet.business_id == business_id)))


def balances_by_account(db: Session, account_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    if not account_ids:
        return {}
    rows = db.execute(
        select(LedgerEntry.account_id, func.coalesce(func.sum(LedgerEntry.delta), 0))
        .where(LedgerEntry.account_id.in_(account_ids))
        .group_by(LedgerEntry.account_id)
    ).all()
    found = {
        account_id: Decimal(str(total)).quantize(Decimal("0.01")) for account_id, total in rows
    }
    return {account_id: found.get(account_id, ZERO) for account_id in account_ids}


def wallet_balance(db: Session, wallet: Wallet) -> Decimal:
    return ledger_service.account_balance(db, wallet.account_id)


def is_business_wallet(wallet: Wallet) -> bool:
    return wallet.role == ROLE_BUSINESS or (
        wallet.role == ROLE_CUSTOM and wallet.purpose == PURPOSE_BUSINESS
    )


def wallet_to_dict(wallet: Wallet, balance: Decimal) -> dict[str, Any]:
    return {
        "id": str(wallet.id),
        "name": wallet.name,
        "role": wallet.role,
        "purpose": wallet.purpose,
        "icon": wallet.icon,
        "color": wallet.color,
        "is_primary": wallet.role == ROLE_PRINCIPAL,
        "is_business": is_business_wallet(wallet),
        "balance": money_str(balance),
    }


def list_wallets(db: Session, business_id: uuid.UUID) -> dict[str, Any]:
    wallets = ensure_default_wallets(db, business_id)
    db.commit()
    balances = balances_by_account(db, [wallet.account_id for wallet in wallets])
    items = [wallet_to_dict(wallet, balances[wallet.account_id]) for wallet in wallets]
    total = sum((balances[wallet.account_id] for wallet in wallets), ZERO)
    return {"items": items, "total": money_str(total), "updated_at": utcnow().isoformat()}


def get_wallet(db: Session, business_id: uuid.UUID, wallet_id: uuid.UUID | str | None) -> Wallet:
    try:
        identifier = uuid.UUID(str(wallet_id))
    except (TypeError, ValueError):
        raise AppError("WALLET_NOT_FOUND", "Billetera no encontrada.", 404) from None
    wallet = db.get(Wallet, identifier)
    if wallet is None or wallet.business_id != business_id or wallet.status != "ACTIVE":
        raise AppError("WALLET_NOT_FOUND", "Billetera no encontrada.", 404)
    return wallet


def clean_name(raw: str | None) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()


def validate_name(db: Session, business_id: uuid.UUID, name: str) -> None:
    if not name:
        raise AppError("NAME_INVALID", "Escribe un nombre para tu billetera.", 422)
    if len(name) < NAME_MIN:
        raise AppError("NAME_INVALID", "El nombre debe tener al menos 3 caracteres.", 422)
    if len(name) > NAME_MAX:
        raise AppError("NAME_INVALID", "Máximo 24 caracteres.", 422)
    taken = db.scalar(
        select(Wallet.id).where(
            Wallet.business_id == business_id,
            Wallet.status == "ACTIVE",
            func.lower(Wallet.name) == name.lower(),
        )
    )
    if taken is not None:
        raise AppError("NAME_TAKEN", "Ya tienes una billetera con ese nombre.", 409)


def create_wallet(
    db: Session,
    business_id: uuid.UUID,
    *,
    name: str,
    purpose: str,
    icon: str | None,
    color: str | None,
    actor_id: uuid.UUID | None,
) -> Wallet:
    ensure_default_wallets(db, business_id)
    name = clean_name(name)
    validate_name(db, business_id, name)
    if purpose not in (PURPOSE_BUSINESS, PURPOSE_SAVINGS):
        raise AppError("PURPOSE_INVALID", "Elige si la billetera es de negocio o de ahorro.", 422)
    customs = db.scalar(
        select(func.count()).where(
            Wallet.business_id == business_id,
            Wallet.role == ROLE_CUSTOM,
            Wallet.status == "ACTIVE",
        )
    )
    if (customs or 0) >= MAX_CUSTOM_WALLETS:
        raise AppError(
            "WALLET_LIMIT",
            f"Puedes tener hasta {MAX_CUSTOM_WALLETS} billeteras adicionales.",
            409,
        )
    position = (
        db.scalar(select(func.max(Wallet.position)).where(Wallet.business_id == business_id)) or 0
    ) + 1
    account = _new_wallet_account(db, business_id)
    wallet = Wallet(
        business_id=business_id,
        account_id=account.id,
        name=name,
        role=ROLE_CUSTOM,
        purpose=purpose,
        icon=(icon or "")[:24] or None,
        color=(color or "")[:16] or None,
        position=position,
        status="ACTIVE",
    )
    db.add(wallet)
    db.flush()
    audit_record(db, business_id, "WALLET_CREATED", "wallet", wallet.id, actor_id=actor_id)
    return wallet


# --------------------------------------------------------------------------- libro


@dataclass(frozen=True)
class Leg:
    account: Account
    delta: Decimal


def _lock_accounts(db: Session, business_id: uuid.UUID, accounts: list[Account]) -> None:
    # Mismo orden que ledger_service.post (cuentas fijas por tipo) y luego WALLET por id,
    # para no generar interbloqueos entre operaciones concurrentes.
    ledger_service._lock_display_accounts(db, business_id)
    wallet_ids = sorted({a.id for a in accounts if a.kind == domain.WALLET})
    if wallet_ids:
        list(
            db.scalars(
                select(Account)
                .where(Account.id.in_(wallet_ids))
                .order_by(Account.id)
                .with_for_update()
            )
        )


def _operation_number(db: Session, environment: str) -> int:
    for _ in range(20):
        candidate = 10_000_000 + secrets.randbelow(90_000_000)
        taken = db.scalar(
            select(Transaction.id).where(
                Transaction.environment == environment,
                Transaction.operation_number == candidate,
            )
        )
        if taken is None:
            return candidate
    raise AppError("OPERATION_NUMBER_EXHAUSTED", "Intenta de nuevo.", 503)


def post_legs(
    db: Session,
    *,
    business_id: uuid.UUID,
    environment: str,
    kind: str,
    amount: Decimal,
    legs: list[Leg],
    source: str,
    occurred_at: datetime,
    description: str,
    provider: str | None = None,
    counterparty_name: str | None = None,
    counterparty_phone_masked: str | None = None,
    note: str | None = None,
    category: str | None = None,
    classification_source: str = domain.EXPLICIT_ACTION,
    actor_id: uuid.UUID | None = None,
) -> Transaction:
    """Publica una operación con asientos explícitos (sin commit)."""
    if sum((leg.delta for leg in legs), ZERO) != ZERO:
        raise AppError("UNBALANCED_ENTRIES", "Asientos desbalanceados.", 500)
    _lock_accounts(db, business_id, [leg.account for leg in legs])
    for leg in legs:
        if leg.delta < 0 and domain.is_debit_account(leg.account.kind):
            available = ledger_service.account_balance(db, leg.account.id)
            if available + leg.delta < 0:
                raise AppError(
                    "INSUFFICIENT_BALANCE",
                    f"No tienes saldo suficiente. Disponible: S/ {money_str(available)}.",
                    409,
                    {"available": money_str(available), "required": money_str(-leg.delta)},
                )

    transaction = Transaction(
        business_id=business_id,
        kind=kind,
        amount=amount,
        medium=domain.DIGITAL,
        currency="PEN",
        status="POSTED",
        source=source,
        environment=environment,
        classification_source=classification_source,
        occurred_at=occurred_at,
        confirmed_at=utcnow(),
        provider=provider,
        description=description,
        operation_number=_operation_number(db, environment),
        counterparty_name=counterparty_name,
        counterparty_phone_masked=counterparty_phone_masked,
        note=note,
        category=category,
        security_code=f"{secrets.randbelow(1000):03d}",
    )
    db.add(transaction)
    db.flush()
    for leg in legs:
        db.add(
            LedgerEntry(
                business_id=business_id,
                transaction_id=transaction.id,
                account_id=leg.account.id,
                delta=leg.delta,
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
        metadata={"kind": kind, "amount": money_str(amount), "medium": domain.DIGITAL},
    )
    ledger_service.schedule_report_revisions(db, business_id, occurred_at)
    return transaction


def _account(db: Session, wallet: Wallet) -> Account:
    account = db.get(Account, wallet.account_id)
    if account is None:  # pragma: no cover - integridad de BD
        raise AppError("ACCOUNT_NOT_FOUND", "Cuenta contable no encontrada.", 500)
    return account


def _external(db: Session, business_id: uuid.UUID) -> Account:
    return ledger_service.get_account(db, business_id, domain.EXTERNAL_CLEARING)


def clean_note(raw: str | None) -> str | None:
    note = clean_name(raw)
    if len(note) > NOTE_MAX:
        raise AppError("NOTE_TOO_LONG", "La descripción puede tener hasta 40 caracteres.", 422)
    return note or None


def transfer(
    db: Session,
    business_id: uuid.UUID,
    environment: str,
    *,
    from_wallet_id: Any,
    to_wallet_id: Any,
    amount: Any,
    note: str | None = None,
    description: str | None = None,
    source: str = domain.USER_DECLARED,
    occurred_at: datetime | None = None,
    actor_id: uuid.UUID | None = None,
) -> Transaction:
    source_wallet = get_wallet(db, business_id, from_wallet_id)
    if to_wallet_id is None:
        raise AppError("DESTINATION_REQUIRED", "Elige la billetera de destino.", 422)
    target_wallet = get_wallet(db, business_id, to_wallet_id)
    if source_wallet.id == target_wallet.id:
        raise AppError("SAME_WALLET", "Elige una billetera de destino distinta.", 422)
    money = Money.parse(amount)
    note = clean_note(note)
    origin, target = _account(db, source_wallet), _account(db, target_wallet)
    if origin.kind == domain.BUSINESS_DIGITAL and target.kind == domain.HOUSEHOLD_DIGITAL:
        kind = domain.HOUSEHOLD_WITHDRAWAL
    elif origin.kind == domain.HOUSEHOLD_DIGITAL and target.kind == domain.BUSINESS_DIGITAL:
        kind = domain.OWNER_CONTRIBUTION
    else:
        kind = domain.WALLET_TRANSFER
    return post_legs(
        db,
        business_id=business_id,
        environment=environment,
        kind=kind,
        amount=money.amount,
        legs=[Leg(origin, -money.amount), Leg(target, money.amount)],
        source=source,
        occurred_at=occurred_at or utcnow(),
        description=description or "Transferencia entre billeteras",
        note=note,
        actor_id=actor_id,
    )


def mask_phone(raw: str | None) -> str | None:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) < 3:
        return None
    return f"*** *** {digits[-3:]}"


def spent_today(db: Session, business_id: uuid.UUID) -> Decimal:
    local_midnight = datetime.combine(to_business(utcnow()).date(), time.min, tzinfo=business_tz())
    value = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.business_id == business_id,
            Transaction.provider == YAPE_PROVIDER,
            Transaction.source == domain.USER_DECLARED,
            Transaction.kind.in_(OUTGOING_YAPE_KINDS),
            Transaction.status == "POSTED",
            Transaction.occurred_at >= local_midnight,
        )
    )
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def yapeo(
    db: Session,
    business_id: uuid.UUID,
    environment: str,
    *,
    from_wallet_id: Any,
    amount: Any,
    counterparty_type: str,
    counterparty_name: str,
    counterparty_phone: str | None = None,
    category: str | None = None,
    message: str | None = None,
    actor_id: uuid.UUID | None = None,
    source: str = domain.USER_DECLARED,
    occurred_at: datetime | None = None,
    enforce_limits: bool = True,
) -> Transaction:
    wallet = get_wallet(db, business_id, from_wallet_id)
    money = Money.parse(amount)
    if enforce_limits:
        per_payment = Decimal(str(settings.payment_limit_pen))
        daily = Decimal(str(settings.daily_limit_pen))
        if money.amount > per_payment:
            raise AppError(
                "PER_PAYMENT_LIMIT",
                f"Límite por yapeo: S/ {per_payment:,.0f}",
                422,
                {"limit": money_str(per_payment)},
            )
        used = spent_today(db, business_id)
        if used + money.amount > daily:
            remaining = max(daily - used, ZERO)
            raise AppError(
                "DAILY_LIMIT",
                f"Superas el límite diario de S/ {daily:,.0f}. Hoy te quedan S/ {money_str(remaining)}",
                422,
                {"remaining": money_str(remaining), "limit": money_str(daily)},
            )
    if category is not None and category not in CATEGORY_LABELS:
        raise AppError("CATEGORY_INVALID", "Categoría no válida.", 422)
    if category is not None and not is_business_wallet(wallet):
        raise AppError(
            "CATEGORY_NOT_ALLOWED",
            "Las categorías solo están disponibles en billeteras de negocio.",
            422,
        )
    name = clean_name(counterparty_name)[:60]
    if not name:
        raise AppError("COUNTERPARTY_REQUIRED", "Elige a quién le yapeas.", 422)
    if counterparty_type not in ("CONTACT", "PHONE", "MERCHANT"):
        raise AppError("COUNTERPARTY_INVALID", "Destinatario inválido.", 422)
    note = clean_note(message)

    origin = _account(db, wallet)
    if origin.kind == domain.BUSINESS_DIGITAL:
        kind = domain.HOUSEHOLD_WITHDRAWAL if category == "FAMILY" else domain.BUSINESS_PAYMENT
    else:
        kind = domain.PERSONAL_PAYMENT
    return post_legs(
        db,
        business_id=business_id,
        environment=environment,
        kind=kind,
        amount=money.amount,
        legs=[Leg(origin, -money.amount), Leg(_external(db, business_id), money.amount)],
        source=source,
        occurred_at=occurred_at or utcnow(),
        description=f"Yapeo a {name}",
        provider=YAPE_PROVIDER,
        counterparty_name=name,
        counterparty_phone_masked=mask_phone(counterparty_phone),
        note=note,
        category=category,
        actor_id=actor_id,
    )


def receive(
    db: Session,
    business_id: uuid.UUID,
    environment: str,
    *,
    to_wallet_id: Any,
    amount: Any,
    from_name: str,
    source: str = domain.SIMULATED,
    occurred_at: datetime | None = None,
    note: str | None = None,
) -> Transaction:
    """Yape recibido (simulado): venta si llega al negocio, ingreso personal si no."""
    wallet = get_wallet(db, business_id, to_wallet_id)
    money = Money.parse(amount)
    target = _account(db, wallet)
    kind = domain.SALE if target.kind == domain.BUSINESS_DIGITAL else domain.PERSONAL_INCOME
    name = clean_name(from_name)[:60] or "Cliente"
    return post_legs(
        db,
        business_id=business_id,
        environment=environment,
        kind=kind,
        amount=money.amount,
        legs=[Leg(target, money.amount), Leg(_external(db, business_id), -money.amount)],
        source=source,
        occurred_at=occurred_at or utcnow(),
        description=f"Yape de {name}",
        provider=YAPE_PROVIDER,
        counterparty_name=name,
        note=clean_note(note),
    )


def archive_wallet(
    db: Session,
    business_id: uuid.UUID,
    environment: str,
    *,
    wallet_id: Any,
    move_to_wallet_id: Any = None,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    wallet = get_wallet(db, business_id, wallet_id)
    if wallet.role == ROLE_PRINCIPAL:
        raise AppError("PRIMARY_LOCKED", "La billetera Principal no se puede eliminar.", 409)
    balance = wallet_balance(db, wallet)
    moved = ZERO
    if balance > 0:
        if not move_to_wallet_id:
            raise AppError(
                "BALANCE_REQUIRES_DESTINATION",
                "Elige a qué billetera mover tu saldo antes de eliminarla.",
                409,
                {"balance": money_str(balance)},
            )
        transfer(
            db,
            business_id,
            environment,
            from_wallet_id=wallet.id,
            to_wallet_id=move_to_wallet_id,
            amount=balance,
            description=f"Saldo de {wallet.name} al eliminarla",
            actor_id=actor_id,
        )
        moved = balance
    hidden = len(movement_ids_only_in(db, wallet))
    wallet.status = "ARCHIVED"
    wallet.archived_at = utcnow()
    db.flush()
    audit_record(db, business_id, "WALLET_ARCHIVED", "wallet", wallet.id, actor_id=actor_id)
    return {
        "archived": True,
        "wallet_id": str(wallet.id),
        "moved_amount": money_str(moved),
        "hidden_movements": hidden,
    }


def movement_ids_only_in(db: Session, wallet: Wallet) -> list[uuid.UUID]:
    """Movimientos que solo involucran a esta billetera (se ocultan al archivarla)."""
    others = [
        w.account_id
        for w in all_wallets(db, wallet.business_id)
        if w.id != wallet.id and w.status == "ACTIVE"
    ]
    own = select(LedgerEntry.transaction_id).where(LedgerEntry.account_id == wallet.account_id)
    stmt = select(Transaction.id).where(
        Transaction.id.in_(own),
        Transaction.kind != domain.OPENING_BALANCE,
    )
    if others:
        stmt = stmt.where(
            ~exists().where(
                LedgerEntry.transaction_id == Transaction.id,
                LedgerEntry.account_id.in_(others),
            )
        )
    return list(db.scalars(stmt))


# --------------------------------------------------------------------------- movimientos


def _wallet_legs(
    db: Session, transaction_ids: list[uuid.UUID], wallets_by_account: dict[uuid.UUID, Wallet]
) -> dict[uuid.UUID, list[tuple[Wallet, Decimal]]]:
    legs: dict[uuid.UUID, list[tuple[Wallet, Decimal]]] = {tid: [] for tid in transaction_ids}
    if not transaction_ids:
        return legs
    rows = db.execute(
        select(LedgerEntry.transaction_id, LedgerEntry.account_id, LedgerEntry.delta).where(
            LedgerEntry.transaction_id.in_(transaction_ids)
        )
    ).all()
    for transaction_id, account_id, delta in rows:
        wallet = wallets_by_account.get(account_id)
        if wallet is not None:
            legs[transaction_id].append((wallet, Decimal(str(delta))))
    return legs


def movement_to_dict(
    transaction: Transaction, legs: list[tuple[Wallet, Decimal]]
) -> dict[str, Any]:
    outflow = [(w, d) for w, d in legs if d < 0]
    inflow = [(w, d) for w, d in legs if d > 0]
    if transaction.kind in TRANSFER_KINDS and outflow and inflow:
        direction = "TRANSFER"
    elif sum((d for _, d in legs), ZERO) < 0:
        direction = "OUT"
    else:
        direction = "IN"

    cp = transaction.counterparty_name
    if direction == "TRANSFER":
        title = transaction.description or "Transferencia entre billeteras"
    elif direction == "OUT":
        title = f"Yapeo a {cp}" if cp else (transaction.description or "Pago")
    elif transaction.kind == domain.SALE and cp:
        title = f"Pago de {cp}"
    elif cp:
        title = f"Yape de {cp}"
    else:
        title = transaction.description or "Ingreso"

    amount = transaction.amount if direction != "OUT" else -transaction.amount
    from_wallet = outflow[0][0] if outflow else None
    to_wallet = inflow[0][0] if inflow else None
    operation = transaction.operation_number or (
        uuid.UUID(str(transaction.id)).int % 90_000_000 + 10_000_000
    )
    return {
        "id": str(transaction.id),
        "operation_number": str(operation),
        "security_code": transaction.security_code or "000",
        "kind": transaction.kind,
        "direction": direction,
        "title": title,
        "amount": money_str(amount),
        "occurred_at": transaction.occurred_at.isoformat(),
        "wallets": [
            {
                "id": str(w.id),
                "name": w.name,
                "role": w.role,
                "purpose": w.purpose,
                "delta": money_str(d),
            }
            for w, d in legs
        ],
        "from_wallet": {"id": str(from_wallet.id), "name": from_wallet.name}
        if from_wallet
        else None,
        "to_wallet": {"id": str(to_wallet.id), "name": to_wallet.name} if to_wallet else None,
        "counterparty_name": cp,
        "counterparty_phone_masked": transaction.counterparty_phone_masked,
        "note": transaction.note,
        "category": transaction.category,
        "category_label": CATEGORY_LABELS.get(transaction.category or ""),
    }


def list_movements(
    db: Session,
    business_id: uuid.UUID,
    *,
    wallet_id: Any = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], str | None]:
    limit = max(1, min(limit, 100))
    wallets = all_wallets(db, business_id)
    by_account = {w.account_id: w for w in wallets}
    if wallet_id:
        visible_accounts = [get_wallet(db, business_id, wallet_id).account_id]
    else:
        visible_accounts = [w.account_id for w in wallets if w.status == "ACTIVE"]
    if not visible_accounts:
        return [], None
    stmt = select(Transaction).where(
        Transaction.business_id == business_id,
        Transaction.status == "POSTED",
        Transaction.kind.notin_(
            (domain.OPENING_BALANCE, domain.REVERSAL, domain.CLASSIFICATION_ADJUSTMENT)
        ),
        exists().where(
            LedgerEntry.transaction_id == Transaction.id,
            LedgerEntry.account_id.in_(visible_accounts),
        ),
    )
    if cursor:
        occurred_at, identifier = ledger_service._decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Transaction.occurred_at < occurred_at,
                and_(Transaction.occurred_at == occurred_at, Transaction.id < identifier),
            )
        )
    rows = list(
        db.scalars(
            stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(limit + 1)
        )
    )
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = ledger_service._encode_cursor(rows[-1])
    legs = _wallet_legs(db, [row.id for row in rows], by_account)
    return [movement_to_dict(row, legs[row.id]) for row in rows], next_cursor


def get_movement(db: Session, business_id: uuid.UUID, transaction_id: Any) -> dict[str, Any]:
    try:
        identifier = uuid.UUID(str(transaction_id))
    except (TypeError, ValueError):
        raise AppError("NOT_FOUND", "Movimiento no encontrado.", 404) from None
    transaction = db.get(Transaction, identifier)
    if transaction is None or transaction.business_id != business_id:
        raise AppError("NOT_FOUND", "Movimiento no encontrado.", 404)
    by_account = {w.account_id: w for w in all_wallets(db, business_id)}
    legs = _wallet_legs(db, [transaction.id], by_account)
    return movement_to_dict(transaction, legs[transaction.id])


# --------------------------------------------------------------------------- datos de demo


PEOPLE = (
    "María Quispe",
    "Carlos Ruiz",
    "Rosa Huamán",
    "Jorge Paredes",
    "Ana Torres",
    "Luis Mendoza",
    "Carmen Flores",
    "Pedro Salazar",
)
SHOPS = ("Bodega Don Lucho", "Mercado Central", "Farmacia del barrio", "Panadería San José")
PROVIDERS = ("Distribuidora Andina", "Proveedor de abarrotes", "Molino La Esperanza")


def _money(rng: random.Random, low: float, high: float, step: str = "0.10") -> Decimal:
    q = Decimal(step)
    value = Decimal(str(low + rng.random() * (high - low)))
    return max((value / q).quantize(Decimal("1")) * q, q).quantize(Decimal("0.01"))


def seed_demo_data(db: Session, business_id: uuid.UUID, environment: str, seed: str) -> None:
    """Saldos y movimientos aleatorios, estables por semilla (el teléfono hasheado).

    Mismo número -> mismos datos iniciales; números distintos -> datos distintos.
    Se publican primero los saldos iniciales, luego ingresos, transferencias y salidas,
    para que ninguna billetera pase por negativo.
    """
    rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:8], "big"))
    wallets = {w.role: w for w in ensure_default_wallets(db, business_id)}
    principal, business, savings = (
        wallets[ROLE_PRINCIPAL],
        wallets[ROLE_BUSINESS],
        wallets[ROLE_SAVINGS],
    )
    targets = {
        principal.id: _money(rng, 400, 2800),
        business.id: _money(rng, 150, 2200),
        savings.id: _money(rng, 50, 1200),
    }

    plan: list[dict[str, Any]] = [
        {
            "type": "in",
            "wallet": business,
            "amount": _money(rng, 8, 150, "0.50"),
            "name": rng.choice(PEOPLE),
        }
        for _ in range(3)
    ]
    plan += [
        {
            "type": "out",
            "wallet": business,
            "amount": _money(rng, 40, 260, "0.50"),
            "name": rng.choice(PROVIDERS),
            "category": rng.choice(("RESTOCK", "LOCAL_SERVICES")),
        },
        {
            "type": "in",
            "wallet": principal,
            "amount": _money(rng, 10, 200, "0.50"),
            "name": rng.choice(PEOPLE),
        },
        {
            "type": "out",
            "wallet": principal,
            "amount": _money(rng, 5, 120, "0.50"),
            "name": rng.choice(PEOPLE),
        },
        {
            "type": "out",
            "wallet": principal,
            "amount": _money(rng, 10, 180, "0.50"),
            "name": rng.choice(SHOPS),
            "merchant": True,
        },
        {
            "type": "transfer",
            "from": principal,
            "to": savings,
            "amount": _money(rng, 50, 200, "10"),
            "description": "Aporte a Vacaciones",
        },
        {
            "type": "transfer",
            "from": business,
            "to": principal,
            "amount": _money(rng, 50, 400, "10"),
            "description": "Transferencia entre billeteras",
        },
    ]

    now_local = to_business(utcnow())
    for index, item in enumerate(plan):
        day = 0 if index == 0 else rng.randrange(0, 9)
        minute = 7 * 60 + rng.randrange(0, 14 * 60)
        when = datetime.combine(
            (now_local - timedelta(days=day)).date(),
            time(minute // 60, minute % 60),
            tzinfo=business_tz(),
        )
        if when > now_local:
            when = now_local - timedelta(minutes=7 * (index + 1))
        item["at"] = when

    net = {wallet_id: ZERO for wallet_id in targets}
    for item in plan:
        if item["type"] == "in":
            net[item["wallet"].id] += item["amount"]
        elif item["type"] == "out":
            net[item["wallet"].id] -= item["amount"]
        else:
            net[item["from"].id] -= item["amount"]
            net[item["to"].id] += item["amount"]

    external = _external(db, business_id)
    opening_at = utcnow() - timedelta(days=15)
    for wallet in (principal, business, savings):
        opening = targets[wallet.id] - net[wallet.id]
        if opening < Decimal("10.00"):
            opening = Decimal("10.00") + _money(rng, 0, 100)
        post_legs(
            db,
            business_id=business_id,
            environment=environment,
            kind=domain.OPENING_BALANCE,
            amount=opening,
            legs=[Leg(_account(db, wallet), opening), Leg(external, -opening)],
            source=domain.SIMULATED,
            occurred_at=opening_at,
            description="Saldo inicial de demo",
        )

    order = {"in": 0, "transfer": 1, "out": 2}
    for item in sorted(plan, key=lambda x: order[x["type"]]):
        if item["type"] == "in":
            receive(
                db,
                business_id,
                environment,
                to_wallet_id=item["wallet"].id,
                amount=item["amount"],
                from_name=item["name"],
                occurred_at=item["at"],
            )
        elif item["type"] == "transfer":
            transfer(
                db,
                business_id,
                environment,
                from_wallet_id=item["from"].id,
                to_wallet_id=item["to"].id,
                amount=item["amount"],
                description=item["description"],
                source=domain.SIMULATED,
                occurred_at=item["at"],
            )
        else:
            yapeo(
                db,
                business_id,
                environment,
                from_wallet_id=item["wallet"].id,
                amount=item["amount"],
                counterparty_type="MERCHANT" if item.get("merchant") else "CONTACT",
                counterparty_name=item["name"],
                category=item.get("category"),
                source=domain.SIMULATED,
                occurred_at=item["at"],
                enforce_limits=False,
            )
