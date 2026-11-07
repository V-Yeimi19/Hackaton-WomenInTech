"""Sesiones demo y vínculo de teléfono con código de un solo uso."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import enforce
from app.core.security import (
    encrypt_phone,
    hash_token,
    new_csrf_token,
    new_token,
    normalize_phone,
    phone_lookup_hash,
)
from app.db.base import utcnow
from app.modules.audit.service import record as audit_record
from app.modules.business.models import Business
from app.modules.identity.models import ChannelLink, LinkChallenge, User
from app.modules.identity.models import Session as SessionModel

settings = get_settings()


def create_demo_session(
    db: Session, display_name: str | None = None
) -> tuple[User, SessionModel, str, str]:
    user = User(display_name=display_name or "Rosa Demo", status="ACTIVE", environment="DEMO")
    db.add(user)
    db.flush()

    token = new_token()
    csrf = new_csrf_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=csrf,
        expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return user, session, token, csrf


def create_link_challenge(db: Session, session: SessionModel) -> tuple[LinkChallenge, str]:
    business = db.scalar(select(Business).where(Business.owner_id == session.user_id))
    if business is None:
        raise AppError("BUSINESS_NOT_ACTIVATED", "Primero activa Mi Negocio.", 409)

    code = secrets.token_urlsafe(12)
    challenge = LinkChallenge(
        session_id=session.id,
        code_hash=hash_token(code),
        expires_at=utcnow() + timedelta(minutes=10),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge, code


def consume_link_challenge(
    db: Session,
    code: str,
    phone: str,
    provider: str = "twilio",
    *,
    commit: bool = True,
) -> tuple[Business, ChannelLink]:
    normalized = normalize_phone(phone)
    enforce(db, phone_lookup_hash(normalized), "consume-link", 5, seconds=600)
    challenge = db.scalar(
        select(LinkChallenge)
        .where(LinkChallenge.code_hash == hash_token(code.strip()))
        .with_for_update()
    )
    if challenge is None:
        raise AppError("INVALID_LINK_CODE", "Código de vínculo inválido.", 400)
    if challenge.consumed_at is not None:
        raise AppError("LINK_CODE_USED", "El código ya fue utilizado.", 409)
    if challenge.expires_at <= utcnow():
        raise AppError("LINK_CODE_EXPIRED", "El código expiró.", 409)
    if challenge.attempts >= 5:
        raise AppError("LINK_ATTEMPTS_EXCEEDED", "Demasiados intentos.", 429)

    session = db.get(SessionModel, challenge.session_id)
    if session is None or session.revoked_at is not None or session.expires_at <= utcnow():
        raise AppError("INVALID_LINK_CODE", "Código de vínculo inválido.", 400)
    business = db.scalar(select(Business).where(Business.owner_id == session.user_id))
    if business is None:
        raise AppError("BUSINESS_NOT_ACTIVATED", "Primero activa Mi Negocio.", 409)

    lookup = phone_lookup_hash(normalized)
    link = db.scalar(
        select(ChannelLink).where(
            ChannelLink.provider == provider,
            ChannelLink.phone_lookup_hash == lookup,
            ChannelLink.environment == business.environment,
        )
    )
    if link is None:
        link = ChannelLink(
            business_id=business.id,
            provider=provider,
            environment=business.environment,
            phone_encrypted=encrypt_phone(normalized),
            phone_lookup_hash=lookup,
            verified_at=utcnow(),
            last_inbound_at=utcnow(),
            status="ACTIVE",
        )
        db.add(link)
    else:
        if link.business_id != business.id:
            raise AppError("PHONE_ALREADY_LINKED", "El teléfono ya tiene un vínculo activo.", 409)
        link.business_id = business.id
        link.phone_encrypted = encrypt_phone(normalized)
        link.verified_at = utcnow()
        link.status = "ACTIVE"

    challenge.consumed_at = utcnow()
    challenge.attempts += 1
    db.flush()
    audit_record(db, business.id, "CHANNEL_LINKED", "channel_link", link.id)
    if commit:
        db.commit()
        db.refresh(link)
    else:
        db.flush()
    return business, link


def find_link_by_phone(db: Session, phone: str, provider: str = "twilio") -> ChannelLink | None:
    try:
        lookup = phone_lookup_hash(phone)
    except ValueError:
        return None
    return db.scalar(
        select(ChannelLink).where(
            ChannelLink.provider == provider,
            ChannelLink.phone_lookup_hash == lookup,
            ChannelLink.status == "ACTIVE",
        )
    )
