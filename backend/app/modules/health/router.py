"""Sondas de vida y disponibilidad (sin datos internos sensibles)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import get_db

router = APIRouter(tags=["health"])
settings = get_settings()
VERSION = "0.1.0"


@router.get("/health/live")
def health_live() -> dict:
    return {
        "status": "ok",
        "service": "mica-api",
        "version": VERSION,
        "environment": settings.app_env,
        "checked_at": utcnow().isoformat(),
    }


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "service": "mica-api",
                "database": "unavailable",
            },
        )
    return {
        "status": "ready",
        "service": "mica-api",
        "database": "ok",
        "checked_at": utcnow().isoformat(),
    }
