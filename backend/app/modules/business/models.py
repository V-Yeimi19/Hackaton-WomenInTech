"""Modelos de negocio y QR de demostración."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Lima")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="DEMO")

    # Campos exclusivos de la demo para el escenario de deuda sintética.
    demo_debt_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    demo_credit_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'PAUSED', 'CLOSED')", name="ck_businesses_status"),
        CheckConstraint("currency = 'PEN'", name="ck_businesses_currency"),
        CheckConstraint("environment IN ('DEMO', 'LIVE')", name="ck_businesses_environment"),
        CheckConstraint(
            "demo_debt_status IN ('UNKNOWN', 'NONE', 'KNOWN_DEBT')",
            name="ck_businesses_demo_debt_status",
        ),
    )


class QrToken(Base):
    __tablename__ = "qr_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
