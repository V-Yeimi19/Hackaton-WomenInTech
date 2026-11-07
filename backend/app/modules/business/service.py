"""Servicio de activación de negocio y consulta de saldos."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token, new_token
from app.db.base import utcnow
from app.modules.audit.service import record as audit_record
from app.modules.business.models import Business, QrToken
from app.modules.business.schemas import ActivationRequest
from app.modules.consents import service as consents_service
from app.modules.consents.models import Preference
from app.modules.identity.models import User
from app.modules.ledger import service as ledger_service

settings = get_settings()


def get_business(db: Session, user_id) -> Business | None:
    return db.scalar(select(Business).where(Business.owner_id == user_id))


def _issue_qr(db: Session, business: Business) -> str:
    raw = new_token()
    db.add(
        QrToken(
            business_id=business.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(days=30),
        )
    )
    return raw


def qr_url(raw_token: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/demo/pay/{raw_token}"


def activate(
    db: Session, user: User, payload: ActivationRequest
) -> tuple[Business, str, dict[str, str]]:
    if not payload.consent_core:
        raise AppError(
            "CONSENT_REQUIRED",
            "Para activar Mi Negocio debes aceptar el tratamiento de datos para las finalidades mostradas.",
            422,
        )

    existing = get_business(db, user.id)
    if existing is not None:
        accounts = ledger_service.ensure_accounts(db, existing.id)
        consents_service.grant(
            db,
            existing.id,
            "CORE_PROCESSING",
            policy_version=payload.policy_version,
            channel=payload.channel,
            commit=False,
        )
        if payload.consent_whatsapp:
            consents_service.grant(
                db,
                existing.id,
                "WHATSAPP_REPORTS",
                policy_version=payload.policy_version,
                channel=payload.channel,
                commit=False,
            )
        if payload.consent_invitations:
            consents_service.grant(
                db,
                existing.id,
                "PRODUCT_INVITATIONS",
                policy_version=payload.policy_version,
                channel=payload.channel,
                commit=False,
            )
        raw_qr = _issue_qr(db, existing)
        db.commit()
        return existing, raw_qr, {kind: str(acc.id) for kind, acc in accounts.items()}

    business = Business(
        owner_id=user.id,
        name=payload.name.strip(),
        category=payload.category,
        status="ACTIVE",
        timezone=settings.app_timezone,
        currency="PEN",
        environment="DEMO",
        demo_debt_status="UNKNOWN",
        demo_credit_active=False,
    )
    db.add(business)
    db.flush()

    accounts = ledger_service.ensure_accounts(db, business.id)
    db.add(
        Preference(
            business_id=business.id,
            reports_enabled=True,
            format="TEXT",
            schedule_local=settings.weekly_report_local_time,
            invitations_enabled=True,
        )
    )

    consents_service.grant(
        db,
        business.id,
        "CORE_PROCESSING",
        policy_version=payload.policy_version,
        channel=payload.channel,
        commit=False,
    )
    if payload.consent_whatsapp:
        consents_service.grant(
            db,
            business.id,
            "WHATSAPP_REPORTS",
            policy_version=payload.policy_version,
            channel=payload.channel,
            commit=False,
        )
    if payload.consent_invitations:
        consents_service.grant(
            db,
            business.id,
            "PRODUCT_INVITATIONS",
            policy_version=payload.policy_version,
            channel=payload.channel,
            commit=False,
        )

    raw_qr = _issue_qr(db, business)
    audit_record(db, business.id, "BUSINESS_ACTIVATED", "business", business.id)
    db.commit()
    db.refresh(business)
    return business, raw_qr, {kind: str(acc.id) for kind, acc in accounts.items()}


def get_balances(db: Session, business: Business) -> dict:
    balances = ledger_service.balances(db, business.id)
    return {
        "business_digital": balances["business_digital"],
        "household_digital": balances["household_digital"],
        "cash_declared": balances["cash_declared"],
        "currency": business.currency,
        "environment": business.environment,
        "updated_at": ledger_service.last_updated(db, business.id),
    }
