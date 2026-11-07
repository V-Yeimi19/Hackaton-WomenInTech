"""Rutas de sesión demo y vínculo de teléfono."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import AuthContext, get_auth_context
from app.core.rate_limit import enforce
from app.db.session import get_db
from app.modules.demo import service as demo_service
from app.modules.identity import service as identity_service
from app.modules.identity.schemas import (
    ChannelLinkChallengeResponse,
    DemoSessionCreate,
    DemoSessionResponse,
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
    return ChannelLinkChallengeResponse(code=code, expires_at=challenge.expires_at)
