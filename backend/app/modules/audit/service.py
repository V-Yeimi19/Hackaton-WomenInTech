"""Servicio de auditoría: append-only, sin secretos ni copias de mensajes."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent


def record(
    db: Session,
    business_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    *,
    actor_type: str = "USER",
    actor_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        business_id=business_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        metadata_json=metadata,
        correlation_id=correlation_id,
    )
    db.add(event)
    return event
