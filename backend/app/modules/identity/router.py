"""Rutas de sesión demo y vínculo de teléfono."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import AuthContext, get_auth_context
from app.core.rate_limit import enforce
from app.db.session import get_db
from app.integrations import telegram_gateway
from app.modules.demo import service as demo_service
from app.modules.identity import service as identity_service
from app.modules.identity.schemas import (
    ChannelLinkChallengeResponse,
    DemoSessionCreate,
    DemoSessionResponse,
    MeResponse,
    PhoneLoginRequest,
    PhoneLoginResponse,
    TelegramStatus,
)

router = APIRouter(tags=["identity"])
settings = get_settings()


@router.post("/demo/sessions", response_model=DemoSessionResponse, status_code=201)
def create_demo_session(
    payload: DemoSessionCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> DemoSessionResponse:
    if settings.app_env != "demo":
        from app.core.errors import AppError

        raise AppError("DEMO_DISABLED", "Demo deshabilitada.", 404)
    enforce(db, request.client.host if request.client else "unknown", "demo-sessions", 30)
    user, session, token, csrf = identity_service.create_demo_session(db, payload.display_name)
    business = demo_service.seed_scenario(db, user, payload.scenario, phone=payload.phone)

    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        "mica_session",
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=settings.public_base_url.startswith("https://"),
    )
    response.set_cookie(
        "mica_csrf",
        csrf,
        max_age=max_age,
        httponly=False,
        samesite="lax",
        secure=settings.public_base_url.startswith("https://"),
    )

    return DemoSessionResponse(
        session_token=token,
        csrf_token=csrf,
        expires_at=session.expires_at,
        user_id=user.id,
        business_id=business.id if business else None,
        environment="DEMO",
        scenario=payload.scenario,
    )


@router.post(
    "/channel-link-challenges",
    response_model=ChannelLinkChallengeResponse,
    status_code=201,
)
def create_channel_link_challenge(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> ChannelLinkChallengeResponse:
    enforce(db, str(ctx.session.id), "link-challenges", 5)
    challenge, code = identity_service.create_link_challenge(db, ctx.session)
    if settings.telegram_enabled and not settings.whatsapp_enabled:
        return ChannelLinkChallengeResponse(
            code=code,
            expires_at=challenge.expires_at,
            channel="telegram",
            telegram_url=telegram_gateway.deep_link(code),
            instructions="Abre el enlace y toca «Iniciar» en Telegram para vincular tu cuenta.",
        )
    return ChannelLinkChallengeResponse(
        code=code,
        expires_at=challenge.expires_at,
        telegram_url=telegram_gateway.deep_link(code) if settings.telegram_enabled else None,
    )


def _set_session_cookies(response: Response, token: str, csrf: str) -> None:
    max_age = settings.session_ttl_hours * 3600
    secure = settings.public_base_url.startswith("https://")
    response.set_cookie(
        "mica_session", token, max_age=max_age, httponly=True, samesite="lax", secure=secure
    )
    response.set_cookie(
        "mica_csrf", csrf, max_age=max_age, httponly=False, samesite="lax", secure=secure
    )


@router.post("/auth/phone-login", response_model=PhoneLoginResponse, status_code=200)
def phone_login(
    payload: PhoneLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> PhoneLoginResponse:
    """Login de demo solo con número (sin clave): mismo número, misma cuenta."""
    if settings.app_env != "demo":
        from app.core.errors import AppError

        raise AppError("DEMO_DISABLED", "Demo deshabilitada.", 404)
    enforce(db, request.client.host if request.client else "unknown", "phone-login", 60)
    user, session, token, csrf, business_id, masked, is_new = identity_service.phone_login(
        db, payload.phone
    )
    _set_session_cookies(response, token, csrf)
    return PhoneLoginResponse(
        session_token=token,
        csrf_token=csrf,
        expires_at=session.expires_at,
        user_id=user.id,
        business_id=business_id,
        phone_masked=masked,
        is_new=is_new,
    )


@router.post("/auth/logout", status_code=204)
def logout(
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    identity_service.logout(db, ctx.session)
    response = Response(status_code=204)
    response.delete_cookie("mica_session")
    response.delete_cookie("mica_csrf")
    return response


@router.get("/me", response_model=MeResponse)
def me(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> MeResponse:
    return MeResponse(
        user_id=ctx.user.id,
        business_id=ctx.business.id if ctx.business else None,
        phone_masked=identity_service.phone_for_user(db, ctx.user.id),
        environment=ctx.user.environment,
        session_expires_at=ctx.session.expires_at,
        telegram=TelegramStatus(
            enabled=settings.telegram_enabled,
            linked=bool(
                settings.telegram_enabled
                and ctx.business
                and identity_service.has_active_link(db, ctx.business.id, "telegram")
            ),
            bot_url=telegram_gateway.bot_url(),
        ),
    )
