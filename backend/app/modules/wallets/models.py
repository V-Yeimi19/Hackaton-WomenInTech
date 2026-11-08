"""Billeteras visibles para la usuaria (cada una respaldada por una cuenta del libro)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow

ROLE_PRINCIPAL = "PRINCIPAL"
ROLE_BUSINESS = "BUSINESS"
ROLE_SAVINGS = "SAVINGS"
ROLE_CUSTOM = "CUSTOM"

PURPOSE_PERSONAL = "PERSONAL"
PURPOSE_BUSINESS = "BUSINESS"
PURPOSE_SAVINGS = "SAVINGS"


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(24), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="ACTIVE")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('PRINCIPAL', 'BUSINESS', 'SAVINGS', 'CUSTOM')", name="ck_wallets_role"
        ),
        CheckConstraint(
            "purpose IN ('PERSONAL', 'BUSINESS', 'SAVINGS')", name="ck_wallets_purpose"
        ),
        CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_wallets_status"),
        Index("ix_wallets_business", "business_id"),
        Index(
            "uq_wallets_business_name_active",
            "business_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )
