"""Modelos de consentimientos y preferencias."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="WEB")
    evidence_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('CORE_PROCESSING', 'WHATSAPP_REPORTS', 'PRODUCT_INVITATIONS', 'BANK_SHARING')",
            name="ck_consents_purpose",
        ),
    )


class Preference(Base):
    __tablename__ = "preferences"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), primary_key=True
    )
    reports_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    format: Mapped[str] = mapped_column(String(10), nullable=False, default="TEXT")
    schedule_local: Mapped[str] = mapped_column(String(5), nullable=False, default="20:00")
    invitations_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (CheckConstraint("format IN ('TEXT', 'AUDIO')", name="ck_preferences_format"),)
