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
from app.modules.insights import service as insights_service
from app.shared.clock import week_start

settings = get_settings()
WEEK = timedelta(days=7)


def enqueue_weekly_reports(db: Session, *, now: datetime | None = None) -> int:
    """Encola el reporte final de la última semana completa de cada negocio.

    Solo considera negocios activos creados antes del cierre de esa semana y
    omite los periodos que ya tienen hechos semanales consolidados.
    """
    now = now or utcnow()
    current_start = week_start(now)
    period_start = current_start - WEEK
    period_end = current_start
    cutoff = period_end + timedelta(minutes=5)
    local_now = now.astimezone(ZoneInfo(settings.app_timezone))
    hour, minute = map(int, settings.weekly_report_local_time.split(":"))
    sunday_cutoff = current_start + timedelta(days=6, hours=hour, minutes=minute)
    preliminary = local_now >= sunday_cutoff
    if preliminary:
        period_start = current_start
        period_end = current_start + WEEK
        cutoff = sunday_cutoff
    elif now < cutoff:
        return 0
    kind = "PRELIMINARY" if preliminary else "WEEKLY_FINAL"

    businesses = list(db.scalars(select(Business).where(Business.status == "ACTIVE")))
    pending_before = db.scalar(
        select(func.count()).select_from(ScheduledJob).where(ScheduledJob.status == "PENDING")
    )
    for business in businesses:
        if business.created_at > cutoff:
            continue
        if (
            not preliminary
            and insights_service.latest_fact(db, business.id, period_start) is not None
        ):
            continue

        dedupe_key = (
            f"weekly-report:{business.id}:{period_start.isoformat()}:{cutoff.isoformat()}:{kind}"
        )
        # ``enqueue`` devuelve el job existente sin duplicarlo; el conteo final
        # se calcula por diferencia para no reportar como nuevo un trabajo que
        # ya estaba pendiente.
        enqueue(
            db,
            business_id=business.id,
            kind=JOB_WEEKLY_REPORT,
            dedupe_key=dedupe_key,
            payload={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "cutoff_at": cutoff.isoformat(),
                "kind": kind,
            },
            run_at=now,
            commit=True,
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
