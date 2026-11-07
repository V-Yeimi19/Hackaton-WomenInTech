"""Rutas de consentimientos y preferencias."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.db.session import get_db
from app.modules.consents import service as consents_service
from app.modules.consents.models import Consent
from app.modules.consents.schemas import (
    ConsentGrantRequest,
    ConsentOut,
    ConsentRevocationRequest,
    PreferencesOut,
    PreferencesPatch,
)

router = APIRouter(tags=["consents"])


def _consent_out(consent: Consent) -> ConsentOut:
    return ConsentOut(
        purpose=consent.purpose,
        policy_version=consent.policy_version,
        granted_at=consent.granted_at,
        revoked_at=consent.revoked_at,
        active=consent.revoked_at is None,
    )


def _prefs_out(prefs) -> PreferencesOut:
    return PreferencesOut(
        reports_enabled=prefs.reports_enabled,
        format=prefs.format,
        schedule_local=prefs.schedule_local,
        invitations_enabled=prefs.invitations_enabled,
        updated_at=prefs.updated_at,
    )


@router.get("/consents", response_model=list[ConsentOut])
def list_consents(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> list[ConsentOut]:
    return [_consent_out(row) for row in consents_service.list_consents(db, ctx.business.id)]


@router.post("/consents/{purpose}/grant", response_model=ConsentOut, status_code=201)
def grant_consent(
    purpose: str,
    payload: ConsentGrantRequest,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> ConsentOut:
    consent = consents_service.grant(
        db,
        ctx.business.id,
        purpose,
        policy_version=payload.policy_version,
        channel=payload.channel,
        evidence_ref=payload.evidence_ref,
    )
    return _consent_out(consent)


@router.post("/consents/{purpose}/revocation", response_model=ConsentOut)
def revoke_consent(
    purpose: str,
    payload: ConsentRevocationRequest,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> ConsentOut:
    consent = consents_service.revoke(
        db,
        ctx.business.id,
        purpose,
        policy_version=payload.policy_version,
        reason=payload.reason,
        actor_id=ctx.user.id,
    )
    return _consent_out(consent)


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> PreferencesOut:
    prefs = consents_service.get_preferences(db, ctx.business.id)
    db.commit()
    db.refresh(prefs)
    return _prefs_out(prefs)


@router.patch("/preferences", response_model=PreferencesOut)
def update_preferences(
    payload: PreferencesPatch,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> PreferencesOut:
    changes = payload.model_dump(exclude_unset=True)
    prefs = consents_service.update_preferences(db, ctx.business.id, changes)
    return _prefs_out(prefs)
