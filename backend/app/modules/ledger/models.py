"""Modelos del libro financiero: cuentas, operaciones, asientos e idempotencia."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        # Las cuentas fijas son únicas por negocio; WALLET admite varias (0005).
        Index(
            "uq_accounts_business_kind_fixed",
            "business_id",
            "kind",
            unique=True,
            postgresql_where=text("kind <> 'WALLET'"),
        ),
        CheckConstraint(
            "kind IN ('BUSINESS_DIGITAL', 'HOUSEHOLD_DIGITAL', 'CASH_DECLARED', "
            "'EXTERNAL_CLEARING', 'WALLET')",
            name="ck_accounts_kind",
        ),
        CheckConstraint("currency = 'PEN'", name="ck_accounts_currency"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    medium: Mapped[str] = mapped_column(String(10), nullable=False, default="DIGITAL")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="POSTED")
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="DEMO")
    classification_source: Mapped[str] = mapped_column(
        String(24), nullable=False, default="EXPLICIT_ACTION"
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    external_transaction_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    inbound_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reversal_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    replacement_for: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    adjustment_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Datos de constancia (0005): número de operación visible, contraparte y mensaje.
    operation_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    counterparty_phone_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(String(40), nullable=True)
    category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    security_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "category IS NULL OR category IN ('RESTOCK', 'LOCAL_SERVICES', 'FAMILY')",
            name="ck_transactions_category",
        ),
        Index(
            "uq_transactions_operation_number",
            "environment",
            "operation_number",
            unique=True,
            postgresql_where=text("operation_number IS NOT NULL"),
        ),
        CheckConstraint("currency = 'PEN'", name="ck_transactions_currency"),
        CheckConstraint("medium IN ('DIGITAL', 'CASH')", name="ck_transactions_medium"),
        CheckConstraint("status IN ('POSTED', 'PENDING', 'FAILED')", name="ck_transactions_status"),
        CheckConstraint(
            "source IN ('SIMULATED', 'USER_DECLARED', 'PROVIDER_CONFIRMED')",
            name="ck_transactions_source",
        ),
        CheckConstraint("environment IN ('DEMO', 'LIVE')", name="ck_transactions_environment"),
        CheckConstraint(
            "classification_source IN ('EXPLICIT_ACTION', 'USER_CONFIRMED', 'RULE', 'PENDING')",
            name="ck_transactions_classification_source",
        ),
        CheckConstraint(
            "kind IN ('SALE', 'BUSINESS_PAYMENT', 'HOUSEHOLD_WITHDRAWAL', 'OWNER_CONTRIBUTION', "
            "'UNKNOWN_OUTFLOW', 'OPENING_BALANCE', 'CLASSIFICATION_ADJUSTMENT', 'REVERSAL', "
            "'PERSONAL_PAYMENT', 'PERSONAL_INCOME', 'WALLET_TRANSFER')",
            name="ck_transactions_kind",
        ),
        UniqueConstraint(
            "provider",
            "environment",
            "external_transaction_id",
            name="uq_transactions_provider_external",
        ),
        UniqueConstraint("reversal_of", name="uq_transactions_reversal_of"),
        Index("ix_transactions_business_occurred", "business_id", "occurred_at", "id"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    delta: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        CheckConstraint("delta <> 0", name="ck_ledger_entries_delta_nonzero"),
        Index("ix_ledger_entries_account_transaction", "account_id", "transaction_id"),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    route: Mapped[str] = mapped_column(String(120), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint("business_id", "route", "key", name="uq_idempotency_business_route_key"),
    )
