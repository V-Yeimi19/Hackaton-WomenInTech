"""Dependencias FastAPI compartidas: sesión de BD y autenticación."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token
from app.db.session import get_db
from app.modules.business.models import Business
from app.modules.identity.models import Session as SessionModel
from app.modules.identity.models import User

settings = get_settings()


@dataclass
class AuthContext:
    session: SessionModel
    user: User
    business: Business | None
    csrf_token: str
    auth_via_cookie: bool


@dataclass
class BusinessContext(AuthContext):
    business: Business


def _extract_token(request: Request) -> tuple[str | None, bool]:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None, False
    cookie = request.cookies.get("mica_session")
    return cookie, bool(cookie)


def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext:
    token, via_cookie = _extract_token(request)
    if not token:
        raise AppError("UNAUTHENTICATED", "Sesión requerida.", 401)

    session = db.scalar(select(SessionModel).where(SessionModel.token_hash == hash_token(token)))
    now = datetime.now(UTC)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise AppError("UNAUTHENTICATED", "Sesión inválida o expirada.", 401)

    user = db.get(User, session.user_id)
    if user is None or user.status != "ACTIVE":
        raise AppError("UNAUTHENTICATED", "Usuaria inválida.", 401)

    business = db.scalar(select(Business).where(Business.owner_id == user.id))

    if request.method not in ("GET", "HEAD", "OPTIONS") and via_cookie and settings.csrf_enabled:
        provided = request.headers.get("X-CSRF-Token", "")
        if not provided or not hmac.compare_digest(provided, session.csrf_token):
            raise AppError("CSRF_INVALID", "Token CSRF inválido.", 403)

    return AuthContext(
        session=session,
        user=user,
        business=business,
        csrf_token=session.csrf_token,
        auth_via_cookie=via_cookie,
    )


def require_business(ctx: AuthContext = Depends(get_auth_context)) -> BusinessContext:
    if ctx.business is None:
        raise AppError(
            "BUSINESS_NOT_ACTIVATED",
            "Primero activa Mi Negocio.",
            409,
        )
    if ctx.business.status != "ACTIVE":
        raise AppError(
            "BUSINESS_NOT_ACTIVE",
            "El negocio no está activo.",
            409,
        )
    return BusinessContext(ctx.session, ctx.user, ctx.business, ctx.csrf_token, ctx.auth_via_cookie)
