"""Consentimientos (append-only) y preferencias."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.audit.service import record as audit_record
from app.modules.business.models import Business
from app.modules.consents.models import Consent, Preference

VALID_PURPOSES = {
    "CORE_PROCESSING",
    "WHATSAPP_REPORTS",
    "PRODUCT_INVITATIONS",
    "BANK_SHARING",
}


def active_consent(db: Session, business_id: uuid.UUID, purpose: str) -> Consent | None:
    return db.scalar(
        select(Consent)
        .where(
            Consent.business_id == business_id,
            Consent.purpose == purpose,
            Consent.revoked_at.is_(None),
        )
        .order_by(Consent.granted_at.desc())
    )


def has_active(db: Session, business_id: uuid.UUID, purpose: str) -> bool:
    return active_consent(db, business_id, purpose) is not None


def grant(
    db: Session,
    business_id: uuid.UUID,
    purpose: str,
    *,
    policy_version: str = "demo-1",
    channel: str = "WEB",
    evidence_ref: str | None = None,
    commit: bool = True,
) -> Consent:
    if purpose not in VALID_PURPOSES:
        raise AppError("INVALID_PURPOSE", "Finalidad desconocida.", 422)

    existing = active_consent(db, business_id, purpose)
    if existing is not None:
        return existing

    consent = Consent(
        business_id=business_id,
        purpose=purpose,
        policy_version=policy_version,
        granted_at=utcnow(),
        channel=channel,
        evidence_ref=evidence_ref,
    )
    db.add(consent)
    db.flush()
    audit_record(
        db, business_id, "CONSENT_GRANTED", "consent", consent.id, metadata={"purpose": purpose}
    )
    if commit:
        db.commit()
        db.refresh(consent)
    return consent


def revoke(
    db: Session,
    business_id: uuid.UUID,
    purpose: str,
    *,
    policy_version: str | None = None,
    reason: str | None = None,
    actor_id: uuid.UUID | None = None,
    commit: bool = True,
) -> Consent:
    if purpose not in VALID_PURPOSES:
        raise AppError("INVALID_PURPOSE", "Finalidad desconocida.", 422)

    consent = active_consent(db, business_id, purpose)
    if consent is None:
        raise AppError(
            "CONSENT_NOT_FOUND", "No hay un consentimiento activo para esa finalidad.", 404
        )

    consent.revoked_at = utcnow()
    if policy_version:
        consent.policy_version = policy_version

    if purpose == "CORE_PROCESSING":
        business = db.get(Business, business_id)
        if business is not None:
            business.status = "PAUSED"

    if purpose in ("WHATSAPP_REPORTS", "CORE_PROCESSING"):
        # Import diferido para no acoplar el módulo de consentimientos a mensajería.
        from app.modules.messaging.models import OutboundMessage

        pending = db.scalars(
            select(OutboundMessage).where(
                OutboundMessage.business_id == business_id,
                OutboundMessage.status.in_(["PENDING", "SENDING", "RETRY"]),
            )
        )
        for message in pending:
            message.status = "CANCELLED"
            message.error_code = "CONSENT_REVOKED"

    audit_record(
        db,
        business_id,
        "CONSENT_REVOKED",
        "consent",
        consent.id,
        actor_id=actor_id,
        reason=reason,
        metadata={"purpose": purpose},
    )
    if commit:
        db.commit()
        db.refresh(consent)
    return consent


def list_consents(db: Session, business_id: uuid.UUID) -> list[Consent]:
    return list(
        db.scalars(
            select(Consent)
            .where(Consent.business_id == business_id)
            .order_by(Consent.granted_at.desc())
        )
    )


def get_preferences(db: Session, business_id: uuid.UUID) -> Preference:
    prefs = db.get(Preference, business_id)
    if prefs is None:
        prefs = Preference(business_id=business_id)
        db.add(prefs)
        db.flush()
    return prefs


def update_preferences(db: Session, business_id: uuid.UUID, changes: dict) -> Preference:
    prefs = get_preferences(db, business_id)
    for key, value in changes.items():
        if value is not None and hasattr(prefs, key):
            setattr(prefs, key, value)
    audit_record(
        db, business_id, "PREFERENCES_UPDATED", "preferences", business_id, metadata=changes
    )
    db.commit()
    db.refresh(prefs)
    return prefs
