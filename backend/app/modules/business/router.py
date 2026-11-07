"""Rutas de activación, negocio y saldos."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, BusinessContext, get_auth_context, require_business
from app.core.errors import AppError
from app.db.session import get_db
from app.modules.business import service as business_service
from app.modules.business.schemas import (
    ActivationRequest,
    ActivationResponse,
    BalancesResponse,
    BusinessOut,
)
from app.modules.consents import service as consents_service

router = APIRouter(tags=["business"])


@router.post("/business/activation", response_model=ActivationResponse, status_code=201)
def activate_business(
    payload: ActivationRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> ActivationResponse:
    business, qr_token, accounts = business_service.activate(db, ctx.user, payload)
    return ActivationResponse(
        business=BusinessOut(
            id=business.id,
            name=business.name,
            category=business.category,
            status=business.status,
            timezone=business.timezone,
            currency=business.currency,
            environment=business.environment,
        ),
        qr_token=qr_token,
        qr_url=business_service.qr_url(qr_token),
        accounts=accounts,
        whatsapp_consent=consents_service.has_active(db, business.id, "WHATSAPP_REPORTS"),
    )


@router.get("/business", response_model=BusinessOut)
def get_business(
    ctx: AuthContext = Depends(get_auth_context),
) -> BusinessOut:
    if ctx.business is None:
        raise AppError("BUSINESS_NOT_ACTIVATED", "Primero activa Mi Negocio.", 404)
    business = ctx.business
    return BusinessOut(
        id=business.id,
        name=business.name,
        category=business.category,
        status=business.status,
        timezone=business.timezone,
        currency=business.currency,
        environment=business.environment,
    )


@router.get("/business/balances", response_model=BalancesResponse)
def get_balances(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> BalancesResponse:
    data = business_service.get_balances(db, ctx.business)
    return BalancesResponse(**data)
