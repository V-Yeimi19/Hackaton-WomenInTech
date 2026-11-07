"""Alertas semanales."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_reports.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint("report_id", "code", name="uq_alerts_report_code"),
        CheckConstraint(
            "code IN ('EXCESS_WITHDRAWAL', 'SALES_DROP', 'PAYMENT_SHORTFALL')",
            name="ck_alerts_code",
        ),
        CheckConstraint("status IN ('ACTIVE', 'RESOLVED')", name="ck_alerts_status"),
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_alerts_severity"),
    )
