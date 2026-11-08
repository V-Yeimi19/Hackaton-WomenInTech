"""Servicio de trabajos durables: encolar, reclamar, ejecutar y reintentar."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.jobs.models import ScheduledJob
from app.modules.audit.service import record as audit_record
from app.modules.business.models import Business
from app.modules.consents import service as consents_service
from app.modules.consents.models import Preference
from app.modules.identity.models import ChannelLink
from app.modules.insights import service as insights_service
from app.modules.insights.models import WeeklyReport
from app.modules.messaging import service as messaging_service
from app.shared.clock import parse_datetime

settings = get_settings()

BACKOFF_SECONDS = [5, 30, 120, 600, 1800]
MAX_ATTEMPTS = len(BACKOFF_SECONDS)
JOB_WEEKLY_REPORT = "WEEKLY_REPORT"


def _backoff(attempts: int) -> datetime:
    seconds = BACKOFF_SECONDS[min(max(attempts - 1, 0), MAX_ATTEMPTS - 1)]
    return utcnow() + timedelta(seconds=seconds)


def enqueue(
    db: Session,
    *,
    business_id: uuid.UUID,
    kind: str,
    dedupe_key: str,
    payload: dict[str, Any] | None = None,
    run_at: datetime | None = None,
    commit: bool = False,
) -> ScheduledJob:
    existing = db.scalar(select(ScheduledJob).where(ScheduledJob.dedupe_key == dedupe_key))
    if existing is not None:
        return existing

    job = ScheduledJob(
        business_id=business_id,
        kind=kind,
        dedupe_key=dedupe_key,
        payload_json=payload or {},
        status="PENDING",
        run_at=run_at or utcnow(),
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(ScheduledJob).where(ScheduledJob.dedupe_key == dedupe_key))
        if existing is not None:
            return existing
        raise

    if commit:
        db.commit()
        db.refresh(job)
    return job


def claim_due_jobs(db: Session, *, limit: int = 10) -> list[ScheduledJob]:
    now = utcnow()
    lease = timedelta(seconds=settings.job_lease_seconds)
    stmt = (
        select(ScheduledJob)
        .where(
            ScheduledJob.status.in_(["PENDING", "RETRY", "PROCESSING"]),
            ScheduledJob.run_at <= now,
            or_(
                ScheduledJob.locked_until.is_(None),
                ScheduledJob.locked_until <= now,
            ),
        )
        .order_by(ScheduledJob.run_at.asc(), ScheduledJob.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    jobs = list(db.scalars(stmt))
    for job in jobs:
        job.status = "PROCESSING"
        job.locked_until = now + lease
        job.attempts += 1
    db.commit()
    return jobs


def finish_job(db: Session, job: ScheduledJob) -> None:
    job.status = "DONE"
    job.locked_until = None
    job.completed_at = utcnow()
    job.last_error = None
    db.commit()


def fail_job(db: Session, job_id: uuid.UUID, error_code: str) -> None:
    db.rollback()
    job = db.get(ScheduledJob, job_id)
    if job is None:
        return
    job.last_error = error_code[:1000]
    job.locked_until = None
    if job.attempts >= MAX_ATTEMPTS:
        job.status = "DEAD"
        job.run_at = utcnow()
    else:
        job.status = "RETRY"
        job.run_at = _backoff(job.attempts)
    db.commit()


def _run_weekly_report(db: Session, job: ScheduledJob) -> dict[str, str]:
    payload = job.payload_json or {}
    business = db.get(Business, job.business_id)
    if business is None or business.status != "ACTIVE":
        audit_record(
            db,
            job.business_id,
            "JOB_SKIPPED",
            "scheduled_job",
            job.id,
            actor_type="SYSTEM",
            metadata={"kind": job.kind, "reason": "BUSINESS_INACTIVE"},
        )
        db.commit()
        return {"skipped": "BUSINESS_INACTIVE"}

    cutoffs = payload.get("cutoff_at")
    cutoff = parse_datetime(cutoffs) if cutoffs else utcnow()
    kind = payload.get("kind", "WEEKLY_FINAL")

    report = (
        db.get(WeeklyReport, uuid.UUID(payload["report_id"])) if payload.get("report_id") else None
    )
    if report is None:
        report = insights_service.generate_report(
            db,
            business,
            cutoff_at=cutoff,
            kind=kind,
            commit=False,
            period_start=parse_datetime(payload["period_start"])
            if payload.get("period_start")
            else None,
            force_revision=bool(payload.get("revision_only")),
        )
        job.payload_json = {**payload, "report_id": str(report.id)}

    link = None
    for provider in messaging_service.enabled_providers():
        link = db.scalar(
            select(ChannelLink)
            .where(
                ChannelLink.business_id == business.id,
                ChannelLink.provider == provider,
                ChannelLink.status == "ACTIVE",
            )
            .order_by(ChannelLink.created_at.asc())
        )
        if link is not None:
            break
    prefs = db.get(Preference, business.id)
    can_send = (
        kind == "PRELIMINARY"
        and not payload.get("revision_only", False)
        and link is not None
        and consents_service.has_active(db, business.id, "WHATSAPP_REPORTS")
        and (prefs is None or prefs.reports_enabled)
    )
    if can_send and link is not None:
        messaging_service.enqueue_outbound(
            db,
            business_id=business.id,
            channel_link_id=link.id,
            body=report.text,
            dedupe_key=f"weekly-report:{business.id}:{report.id}:{link.id}",
            report_id=report.id,
            commit=False,
        )

    audit_record(
        db,
        business.id,
        "REPORT_GENERATED",
        "weekly_report",
        report.id,
        actor_type="SYSTEM",
        metadata={
            "kind": report.kind,
            "revision": report.revision,
            "cutoff_at": cutoff.isoformat(),
            "queued_message": bool(can_send),
        },
    )
    db.commit()
    return {
        "report_id": str(report.id),
        "queued_message": "true" if can_send else "false",
    }


def run_job(db: Session, job: ScheduledJob) -> dict[str, str]:
    if job.kind == JOB_WEEKLY_REPORT:
        return _run_weekly_report(db, job)
    raise ValueError(f"Trabajo desconocido: {job.kind}")


def run_due_jobs(db: Session, *, limit: int = 10) -> int:
    jobs = claim_due_jobs(db, limit=limit)
    for job in jobs:
        try:
            run_job(db, job)
            finish_job(db, job)
        except Exception as exc:  # el fallo se persiste y se reintenta con backoff
            fail_job(db, job.id, exc.__class__.__name__)
    return len(jobs)


__all__ = [
    "JOB_WEEKLY_REPORT",
    "claim_due_jobs",
    "enqueue",
    "fail_job",
    "finish_job",
    "run_due_jobs",
    "run_job",
]
