"""Planificador: crea trabajos idempotentes para reportes semanales.

El contrato del README exige una clave de deduplicación por
``business_id + period_start + cutoff_at + kind``. La tabla
``scheduled_jobs`` tiene un índice único sobre esa clave, así que dos
schedulers concurrentes no duplican el trabajo.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.jobs.models import ScheduledJob
from app.jobs.service import JOB_WEEKLY_REPORT, enqueue
from app.modules.business.models import Business
from app.modules.consents.models import Preference
from app.modules.insights import service as insights_service
from app.shared.clock import week_start

settings = get_settings()
WEEK = timedelta(days=7)


def report_slot(db: Session, business: Business, current_start: datetime) -> datetime:
    """Momento de esta semana en que el negocio quiere su reporte (UTC).

    Usa el día y la hora que la usuaria le dio a Mica (preferences); sin
    preferencia, el domingo a la hora de WEEKLY_REPORT_LOCAL_TIME.
    """
    prefs = db.get(Preference, business.id)
    weekday = prefs.schedule_weekday if prefs is not None else 6
    hhmm = prefs.schedule_local if prefs is not None else settings.weekly_report_local_time
    hour, minute = map(int, hhmm.split(":"))
    # current_start es el lunes 00:00 de Lima; Lima no tiene horario de verano.
    return current_start + timedelta(days=weekday, hours=hour, minutes=minute)


def _enqueue(
    db: Session,
    business: Business,
    *,
    period_start: datetime,
    cutoff: datetime,
    kind: str,
    now: datetime,
) -> None:
    dedupe_key = (
        f"weekly-report:{business.id}:{period_start.isoformat()}:{cutoff.isoformat()}:{kind}"
    )
    # ``enqueue`` devuelve el job existente sin duplicarlo; el conteo final se
    # calcula por diferencia para no reportar como nuevo un trabajo pendiente.
    enqueue(
        db,
        business_id=business.id,
        kind=JOB_WEEKLY_REPORT,
        dedupe_key=dedupe_key,
        payload={
            "period_start": period_start.isoformat(),
            "period_end": (period_start + WEEK).isoformat(),
            "cutoff_at": cutoff.isoformat(),
            "kind": kind,
        },
        run_at=now,
        commit=True,
    )


def enqueue_weekly_reports(db: Session, *, now: datetime | None = None) -> int:
    """Encola los reportes semanales de cada negocio activo.

    - Reporte que se envía (``PRELIMINARY``): cuando llega el día y la hora que
      cada negocio eligió. De lunes a jueves cubre la semana anterior completa;
      de viernes a domingo, la semana en curso hasta ese momento.
    - Consolidación interna (``WEEKLY_FINAL``, sin mensaje): el lunes 00:05 de la
      última semana completa, como antes, si aún no tiene hechos consolidados.
    """
    now = now or utcnow()
    current_start = week_start(now)
    final_start = current_start - WEEK
    final_cutoff = current_start + timedelta(minutes=5)
    hour, minute = map(int, settings.weekly_report_local_time.split(":"))
    default_slot = current_start + timedelta(days=6, hours=hour, minutes=minute)
    consolidate = final_cutoff <= now < default_slot

    businesses = list(db.scalars(select(Business).where(Business.status == "ACTIVE")))
    pending_before = db.scalar(
        select(func.count()).select_from(ScheduledJob).where(ScheduledJob.status == "PENDING")
    )
    for business in businesses:
        slot = report_slot(db, business, current_start)
        if now >= slot and business.created_at <= slot:
            weekday = slot.astimezone(ZoneInfo(settings.app_timezone)).weekday()
            period_start = current_start if weekday >= 4 else current_start - WEEK
            _enqueue(
                db, business, period_start=period_start, cutoff=slot, kind="PRELIMINARY", now=now
            )
        if (
            consolidate
            and business.created_at <= final_cutoff
            and insights_service.latest_fact(db, business.id, final_start) is None
        ):
            _enqueue(
                db,
                business,
                period_start=final_start,
                cutoff=final_cutoff,
                kind="WEEKLY_FINAL",
                now=now,
            )
    pending_after = db.scalar(
        select(func.count()).select_from(ScheduledJob).where(ScheduledJob.status == "PENDING")
    )
    return max(int(pending_after or 0) - int(pending_before or 0), 0)


def run_forever() -> None:
    while True:
        db = SessionLocal()
        try:
            enqueue_weekly_reports(db)
        finally:
            db.close()
        time.sleep(settings.scheduler_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scheduler de Mica")
    parser.add_argument("--once", action="store_true", help="Ejecuta un solo ciclo")
    args = parser.parse_args()

    if args.once:
        db = SessionLocal()
        try:
            count = enqueue_weekly_reports(db)
            print(f"Trabajos encolados: {count}")
        finally:
            db.close()
        return

    try:
        run_forever()
    except KeyboardInterrupt:
        print("Scheduler detenido.")


if __name__ == "__main__":
    main()
