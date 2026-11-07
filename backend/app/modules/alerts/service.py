"""Persistencia y consulta de alertas."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.alerts.domain import AlertData
from app.modules.alerts.models import Alert


def persist_for_report(
    db: Session,
    business_id: uuid.UUID,
    report_id: uuid.UUID,
    alerts: list[AlertData],
) -> list[Alert]:
    persisted: list[Alert] = []
    for data in alerts:
        existing = db.scalar(
            select(Alert).where(Alert.report_id == report_id, Alert.code == data.code)
        )
        if existing is not None:
            persisted.append(existing)
            continue
        alert = Alert(
            business_id=business_id,
            report_id=report_id,
            code=data.code,
            severity=data.severity,
            evidence_json=data.evidence,
            status="ACTIVE",
        )
        db.add(alert)
        persisted.append(alert)
    db.flush()
    return persisted


def list_for_report(db: Session, report_id: uuid.UUID) -> list[Alert]:
    return list(
        db.scalars(
            select(Alert).where(Alert.report_id == report_id).order_by(Alert.created_at.asc())
        )
    )


def active_for_business(db: Session, business_id: uuid.UUID) -> list[Alert]:
    return list(
        db.scalars(
            select(Alert)
            .where(Alert.business_id == business_id, Alert.status == "ACTIVE")
            .order_by(Alert.created_at.desc())
        )
    )


def resolve_for_report(db: Session, report_id: uuid.UUID) -> None:
    for alert in db.scalars(select(Alert).where(Alert.report_id == report_id)):
        alert.status = "RESOLVED"
