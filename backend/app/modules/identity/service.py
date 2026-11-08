"""Sesiones demo y vínculo de teléfono con código de un solo uso."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import enforce
from app.core.security import (
    channel_address,
    channel_lookup_hash,
    decrypt_phone,
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
from app.modules.identity.models import ChannelLink, LinkChallenge, User, UserPhone
from app.modules.identity.models import Session as SessionModel

settings = get_settings()


def issue_session(db: Session, user: User) -> tuple[SessionModel, str, str]:
    """Crea una sesión (el token solo se guarda hasheado). No hace commit."""
    token = new_token()
    csrf = new_csrf_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=csrf,
        expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.flush()
    return session, token, csrf


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
    """Vincula una dirección del canal (teléfono o chat_id de Telegram) al negocio."""
    normalized = channel_address(provider, phone)
    lookup = channel_lookup_hash(provider, normalized)
    enforce(db, lookup, "consume-link", 5, seconds=600)
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


def find_link_by_phone(
    db: Session,
    phone: str,
    provider: str = "twilio",
    *,
    business_id: uuid.UUID | None = None,
    environment: str | None = None,
) -> ChannelLink | None:
    try:
        lookup = channel_lookup_hash(provider, phone)
    except ValueError:
        return None
    conditions = [
        ChannelLink.provider == provider,
        ChannelLink.phone_lookup_hash == lookup,
        ChannelLink.status == "ACTIVE",
    ]
    # Un evento con negocio conocido no debe resolver el vínculo de otro
    # negocio aunque el teléfono coincida (aislamiento por negocio/entorno).
    if business_id is not None:
        conditions.append(ChannelLink.business_id == business_id)
    if environment is not None:
        conditions.append(ChannelLink.environment == environment)
    return db.scalar(select(ChannelLink).where(*conditions))


def has_active_link(db: Session, business_id: uuid.UUID, provider: str) -> bool:
    return (
        db.scalar(
            select(ChannelLink.id).where(
                ChannelLink.business_id == business_id,
                ChannelLink.provider == provider,
                ChannelLink.status == "ACTIVE",
            )
        )
        is not None
    )


PERU_MOBILE = re.compile(r"^\+519\d{8}$")


def mask_phone(normalized: str) -> str:
    return f"*** *** {normalized[-3:]}"


def phone_login(
    db: Session, raw_phone: str
) -> tuple[User, SessionModel, str, str, uuid.UUID, str, bool]:
    """Login de demo solo con número: mismo número -> misma cuenta.

    La primera vez crea la usuaria, activa Mi Negocio, crea las billeteras base y
    siembra saldos y movimientos aleatorios estables por número. Todo en una sola
    transacción, serializada por número con un advisory lock.
    """
    from app.modules.demo.service import _create_business
    from app.modules.wallets import service as wallets_service

    try:
        normalized = normalize_phone(raw_phone)
    except ValueError:
        normalized = ""
    if not PERU_MOBILE.match(normalized):
        raise AppError("INVALID_PHONE", "Ingresa un celular de 9 dígitos que empiece con 9.", 422)
    lookup = phone_lookup_hash(normalized)
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"phone-login:{lookup}"},
    )

    is_new = False
    record = db.scalar(
        select(UserPhone).where(
            UserPhone.phone_lookup_hash == lookup, UserPhone.environment == "DEMO"
        )
    )
    if record is not None:
        user = db.get(User, record.user_id)
        if user is None or user.status != "ACTIVE":
            raise AppError("USER_DISABLED", "Esta cuenta no está disponible.", 403)
    else:
        is_new = True
        user = User(display_name="Yaper@", status="ACTIVE", environment="DEMO")
        db.add(user)
        db.flush()
        db.add(
            UserPhone(
                user_id=user.id,
                environment="DEMO",
                phone_encrypted=encrypt_phone(normalized),
                phone_lookup_hash=lookup,
            )
        )
        db.flush()

    business = db.scalar(select(Business).where(Business.owner_id == user.id))
    if business is None:
        business = _create_business(db, user, name="Mi Negocio", category="bodega")
        audit_record(db, business.id, "BUSINESS_ACTIVATED", "business", business.id)
    if not wallets_service.all_wallets(db, business.id):
        # Datos aleatorios estables: la semilla es el hash HMAC del número.
        wallets_service.seed_demo_data(db, business.id, business.environment, seed=lookup)
    _ensure_channel_link(db, business, normalized, lookup)

    session, token, csrf = issue_session(db, user)
    db.commit()
    db.refresh(session)
    return user, session, token, csrf, business.id, mask_phone(normalized), is_new


def _ensure_channel_link(db: Session, business: Business, normalized: str, lookup: str) -> None:
    """Vincula el número al negocio para que el agente lo reconozca por WhatsApp.

    En modo Twilio real no se vincula automáticamente: se exige VINCULAR <código>
    desde el propio teléfono (mismo criterio que los escenarios de demo).
    """
    if settings.messaging_mode == "twilio":
        return
    existing = db.scalar(
        select(ChannelLink).where(
            ChannelLink.provider == "twilio",
            ChannelLink.phone_lookup_hash == lookup,
            ChannelLink.environment == business.environment,
        )
    )
    if existing is not None:
        return
    db.add(
        ChannelLink(
            business_id=business.id,
            provider="twilio",
            environment=business.environment,
            phone_encrypted=encrypt_phone(normalized),
            phone_lookup_hash=lookup,
            verified_at=utcnow(),
            last_inbound_at=utcnow(),
            status="ACTIVE",
        )
    )
    db.flush()


def logout(db: Session, session: SessionModel) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        db.commit()


def phone_for_user(db: Session, user_id: uuid.UUID) -> str | None:
    record = db.scalar(select(UserPhone).where(UserPhone.user_id == user_id))
    if record is None:
        return None
    try:
        return mask_phone(decrypt_phone(record.phone_encrypted))
    except ValueError:
        return None
