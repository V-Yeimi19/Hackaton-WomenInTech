"""Trabajos durables persistidos en PostgreSQL.

No se usa un broker externo: el scheduler inserta filas y el worker las reclama
con ``SELECT ... FOR UPDATE SKIP LOCKED`` y un lease temporal. Si el proceso cae,
el trabajo vuelve a estar disponible cuando vence el lease.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'DONE', 'RETRY', 'DEAD')",
            name="ck_scheduled_jobs_status",
        ),
        Index("ix_scheduled_jobs_status_run", "status", "run_at"),
    )
