"""Evaluaciones ilustrativas de oportunidades (ahorro/crédito)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class OpportunityEvaluation(Base):
    __tablename__ = "opportunity_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_reports.id"), nullable=False, unique=True
    )
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    product_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reasons_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    stable_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    demo_debt_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    weekly_installment_cap: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        CheckConstraint("is_simulated = true", name="ck_opportunity_is_simulated"),
        CheckConstraint(
            "product_type IS NULL OR product_type IN ('SAVINGS', 'CREDIT')",
            name="ck_opportunity_product_type",
        ),
    )
