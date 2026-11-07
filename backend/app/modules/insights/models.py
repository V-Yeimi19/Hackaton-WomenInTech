"""Hechos semanales y snapshots de reportes."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class WeeklyFact(Base):
    __tablename__ = "weekly_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    week_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    payments: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    withdrawals: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    contributions: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    operating_flow: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    coverage_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="RECORDED_ONLY"
    )
    stable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    data_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "business_id", "week_start", "revision", name="uq_weekly_facts_business_week_revision"
        ),
        Index("ix_weekly_facts_business_week", "business_id", "week_start"),
    )


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    coverage_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    advice_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "period_start",
            "data_cutoff_at",
            "kind",
            "revision",
            name="uq_weekly_reports_business_period_cutoff_kind_rev",
        ),
        CheckConstraint("kind IN ('PRELIMINARY', 'WEEKLY_FINAL')", name="ck_weekly_reports_kind"),
        Index("ix_weekly_reports_business_period", "business_id", "period_start"),
    )
