"""Cuotas compartidas entre procesos, persistidas en PostgreSQL."""

import hashlib

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utcnow


def enforce(db: Session, subject: str, scope: str, limit: int, seconds: int = 60) -> None:
    window = int(utcnow().timestamp()) // seconds
    key = hashlib.sha256(f"{scope}:{subject}".encode()).hexdigest()
    hits = db.scalar(
        text("""
        INSERT INTO request_quotas (key, "window", hits) VALUES (:key, :window, 1)
        ON CONFLICT (key) DO UPDATE SET
          hits = CASE WHEN request_quotas."window" = EXCLUDED."window"
                      THEN request_quotas.hits + 1 ELSE 1 END,
          "window" = EXCLUDED."window"
        RETURNING hits
    """),
        {"key": key, "window": window},
    )
    db.commit()
    if hits > limit:
        raise AppError("RATE_LIMIT_EXCEEDED", "Demasiadas solicitudes. Intenta más tarde.", 429)
