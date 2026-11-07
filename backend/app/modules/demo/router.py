"""Ayudas de demostración: simulación de cobros, WhatsApp y QR.

Estas rutas son exclusivas de ``DEMO`` y no sustituyen los webhooks firmados.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import BusinessContext, require_business
from app.core.errors import AppError
from app.core.rate_limit import enforce
from app.core.security import decrypt_phone, hash_token
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.business.models import Business, QrToken
from app.modules.identity.models import ChannelLink
from app.modules.ledger import service as ledger_service
from app.modules.messaging import service as messaging_service
from app.modules.messaging.models import InboundEvent, OutboundMessage
from app.shared.money import Money

router = APIRouter(tags=["demo"])
settings = get_settings()


class SimulateSaleRequest(BaseModel):
    amount: str = Field(description="Importe decimal como cadena, por ejemplo 120.00")


class SimulateWhatsappRequest(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    phone: str | None = None


def _simulator_event(business: Business, amount: str, *, event_id: str | None = None) -> dict:
    money = Money.parse(amount, business.currency)
    return {
        "schema_version": "1.0",
        "event_id": event_id or f"demo-event-{uuid.uuid4().hex[:12]}",
        "event_type": "transaction.confirmed",
        "environment": "DEMO",
        "external_transaction_id": f"demo-tx-{uuid.uuid4().hex[:12]}",
        "business_reference": str(business.id),
        "kind": "SALE",
        "amount": money.to_str(),
        "currency": "PEN",
        "occurred_at": utcnow().isoformat(),
        "source": "SIMULATED",
    }


def _process_sale(db: Session, business: Business, amount: str) -> InboundEvent:
    payload = _simulator_event(business, amount)
    event, duplicate = messaging_service.persist_inbound(
        db,
        provider="simulator",
        event_id=payload["event_id"],
        payload=payload,
        business_id=business.id,
    )
    if not duplicate:
        messaging_service.process_inbound(db, event)
    refreshed = db.get(InboundEvent, event.id)
    return refreshed or event


@router.post("/demo/simulate-sale")
def simulate_sale(
    payload: SimulateSaleRequest,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> dict:
    enforce(db, str(ctx.session.id), "demo-simulation", 60)
    business = ctx.business
    event = _process_sale(db, business, payload.amount)
    return {
        "event_id": event.event_id,
        "status": event.status,
        "balances": ledger_service.balances(db, business.id),
        "message": "Cobro simulado por el QR demo; el efecto es idempotente por event_id.",
    }


@router.post("/demo/simulate-whatsapp")
def simulate_whatsapp(
    payload: SimulateWhatsappRequest,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> dict:
    enforce(db, str(ctx.session.id), "demo-simulation", 60)
    business = ctx.business
    if settings.messaging_mode == "twilio":
        raise AppError("SIMULATION_DISABLED", "Usa el webhook firmado para WhatsApp real.", 403)
    if payload.phone:
        link = None
        from app.core.security import normalize_phone, phone_lookup_hash

        lookup = phone_lookup_hash(normalize_phone(payload.phone))
        link = db.scalar(
            select(ChannelLink).where(
                ChannelLink.provider == "twilio",
                ChannelLink.phone_lookup_hash == lookup,
                ChannelLink.business_id == business.id,
                ChannelLink.status == "ACTIVE",
                ChannelLink.environment == business.environment,
            )
        )
    else:
        link = db.scalar(
            select(ChannelLink)
            .where(
                ChannelLink.business_id == business.id,
                ChannelLink.status == "ACTIVE",
            )
            .order_by(ChannelLink.created_at.asc())
        )
    if link is None:
        raise AppError(
            "CHANNEL_NOT_LINKED",
            "Primero vincula un teléfono de prueba (VINCULAR <código>).",
            409,
        )

    phone = decrypt_phone(link.phone_encrypted)
    event_id = f"demo-wa-{uuid.uuid4().hex[:12]}"
    inbound_payload = {
        "MessageSid": event_id,
        "AccountSid": settings.twilio_account_sid or "ACdemo",
        "From": phone,
        "To": settings.twilio_whatsapp_from,
        "Body": payload.body,
        "NumMedia": "0",
    }
    event, duplicate = messaging_service.persist_inbound(
        db, provider="twilio", event_id=event_id, payload=inbound_payload
    )
    if not duplicate:
        messaging_service.process_inbound(db, event)
        messaging_service.deliver_pending(db)

    messages = list(
        db.scalars(
            select(OutboundMessage)
            .where(OutboundMessage.business_id == business.id)
            .order_by(OutboundMessage.created_at.desc())
            .limit(5)
        )
    )
    return {
        "event_id": event_id,
        "status": "DONE" if not duplicate else "DUPLICATE",
        "messages": [messaging_service.message_to_dict(row) for row in messages],
    }


@router.get("/demo/messages")
def list_messages(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = list(
        db.scalars(
            select(OutboundMessage)
            .where(OutboundMessage.business_id == ctx.business.id)
            .order_by(OutboundMessage.created_at.desc())
            .limit(20)
        )
    )
    return [messaging_service.message_to_dict(row) for row in rows]


@router.get("/demo/inbox")
def list_inbox(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = list(
        db.scalars(
            select(InboundEvent)
            .where(InboundEvent.business_id == ctx.business.id)
            .order_by(InboundEvent.received_at.desc())
            .limit(20)
        )
    )
    return [
        {
            "event_id": row.event_id,
            "provider": row.provider,
            "status": row.status,
            "attempts": row.attempts,
            "received_at": row.received_at.isoformat(),
            "error_code": row.error_code,
        }
        for row in rows
    ]


@router.post("/demo/qr/{token}/sales")
def simulate_qr_sale(
    token: str,
    payload: SimulateSaleRequest,
    db: Session = Depends(get_db),
):
    enforce(db, hash_token(token), "qr-simulation", 60)
    qr = db.scalar(
        select(QrToken).where(QrToken.token_hash == hash_token(token), QrToken.revoked_at.is_(None))
    )
    now = utcnow()
    if qr is None or (qr.expires_at is not None and qr.expires_at <= now):
        raise AppError("QR_NOT_FOUND", "QR demo inválido o expirado.", 404)
    business = db.get(Business, qr.business_id)
    if business is None or business.status != "ACTIVE":
        raise AppError("BUSINESS_NOT_ACTIVE", "El negocio no está activo.", 409)

    event = _process_sale(db, business, payload.amount)
    return JSONResponse(
        status_code=202,
        content={
            "event_id": event.event_id,
            "status": event.status,
            "business_id": str(business.id),
            "message": "Cobro QR demo recibido.",
        },
    )
