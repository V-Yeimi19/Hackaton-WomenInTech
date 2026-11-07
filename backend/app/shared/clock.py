"""Reloj y límites de semana en la zona de negocio (America/Lima)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings

settings = get_settings()


def business_tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_business(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(business_tz())


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=business_tz())
    return dt.astimezone(UTC)


def parse_datetime(value: str | datetime | None, default: datetime | None = None) -> datetime:
    if value is None:
        return default or now_utc()
    if isinstance(value, datetime):
        return to_utc(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Fecha ISO 8601 inválida") from exc
    return to_utc(parsed)


def week_start(dt: datetime) -> datetime:
    """Lunes 00:00 America/Lima del periodo que contiene `dt`, en UTC."""
    local = to_business(dt)
    monday = local.date() - timedelta(days=local.weekday())
    local_start = datetime.combine(monday, time.min).replace(tzinfo=business_tz())
    return local_start.astimezone(UTC)


def week_end(dt: datetime) -> datetime:
    """Lunes siguiente 00:00 America/Lima (extremo final excluido), en UTC."""
    return week_start(dt) + timedelta(days=7)


def week_start_local_date(dt: datetime) -> date:
    return week_start(dt).astimezone(business_tz()).date()


def add_weeks(dt: datetime, weeks: int) -> datetime:
    return dt + timedelta(weeks=weeks)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat()


def lima_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(business_tz()).isoformat()
