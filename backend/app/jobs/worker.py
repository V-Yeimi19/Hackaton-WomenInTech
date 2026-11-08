"""Worker durable de Mica.

Procesa inbox, trabajos programados y outbox. No usa broker externo: todo el
estado vive en PostgreSQL y cada fase es idempotente. Puede ejecutarse como
proceso separado de la API o convivir con ella en la demo mínima.
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.jobs import scheduler
from app.jobs.service import run_due_jobs
from app.modules.ledger.models import IdempotencyRecord
from app.modules.messaging.service import (
    deliver_pending,
    poll_telegram,
    process_pending_inbound,
)

settings = get_settings()
logger = logging.getLogger("mica.worker")


def cleanup_expired_idempotency(db: Session) -> int:
    result = db.execute(
        delete(IdempotencyRecord)
        .where(IdempotencyRecord.expires_at < utcnow())
        .returning(IdempotencyRecord.id)
    )
    count = len(result.all())
    db.commit()
    return count


def run_once(db: Session) -> dict[str, int]:
    telegram = poll_telegram(db)
    inbound = process_pending_inbound(db, limit=settings.worker_batch_size)
    jobs = run_due_jobs(db, limit=settings.worker_batch_size)
    outbound = deliver_pending(db, limit=settings.worker_batch_size)
    purged = cleanup_expired_idempotency(db)
    return {
        "telegram": telegram,
        "inbound": inbound,
        "jobs": jobs,
        "outbound": outbound,
        "idempotency_purged": purged,
    }


def run_forever(*, with_scheduler: bool = True) -> None:
    last_schedule = 0.0
    while True:
        db = SessionLocal()
        try:
            if with_scheduler:
                now_monotonic = time.monotonic()
                if now_monotonic - last_schedule >= settings.scheduler_interval_seconds:
                    scheduler.enqueue_weekly_reports(db)
                    last_schedule = now_monotonic
            stats = run_once(db)
            if any(stats.values()):
                logger.info("worker.cycle %s", stats)
        except Exception as exc:
            logger.error("worker.cycle_failed type=%s", type(exc).__name__)
            db.rollback()
        finally:
            db.close()
        time.sleep(settings.worker_poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker durable de Mica")
    parser.add_argument("--once", action="store_true", help="Ejecuta un solo ciclo")
    parser.add_argument(
        "--no-scheduler",
        action="store_true",
        help="No ejecuta el scheduler dentro del proceso worker",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.once:
        db = SessionLocal()
        try:
            print(run_once(db))
        finally:
            db.close()
        return

    with_scheduler = settings.run_scheduler_in_worker and not args.no_scheduler
    try:
        run_forever(with_scheduler=with_scheduler)
    except KeyboardInterrupt:
        logger.info("worker.stopped")


if __name__ == "__main__":
    main()
