"""Webhooks del simulador, de Twilio WhatsApp y de Telegram."""

from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    verify_simulator_signature,
    verify_telegram_secret,
    verify_twilio_signature,
)
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.messaging import service as messaging_service
from app.modules.messaging.schemas import SimulatorEvent

router = APIRouter(tags=["webhooks"])
settings = get_settings()


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@router.post("/webhooks/simulator/transactions")
async def simulator_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw = await request.body()
    timestamp = request.headers.get("X-Mica-Timestamp", "")
    signature = request.headers.get("X-Mica-Signature", "")
    if not verify_simulator_signature(timestamp, raw, signature):
        raise AppError("INVALID_SIGNATURE", "Firma del simulador inválida.", 403)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AppError("INVALID_JSON", "Cuerpo JSON inválido.", 400) from exc

    try:
        event_model = SimulatorEvent.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    business_id = None
    try:
        business_id = uuid.UUID(str(payload.get("business_reference")))
    except (ValueError, TypeError):
        business_id = None

    try:
        event, duplicate = messaging_service.persist_inbound(
            db,
            provider="simulator",
            event_id=event_model.event_id,
            payload=payload,
            business_id=business_id,
        )
    except SQLAlchemyError as exc:
        raise AppError(
            "INBOX_UNAVAILABLE",
            "No se pudo persistir el evento. Reintenta.",
            503,
        ) from exc

    if duplicate:
        return JSONResponse(
            status_code=200,
            content={
                "received": True,
                "event_id": event.event_id,
                "status": "DUPLICATE",
                "message": "Evento ya recibido; no genera un nuevo efecto.",
            },
        )

    if settings.process_inbox_inline:
        messaging_service.process_inbound(db, event)

    return JSONResponse(
        status_code=202,
        content={
            "received": True,
            "event_id": event.event_id,
            "status": "RECEIVED",
            "message": "Evento persistido para procesamiento durable.",
        },
    )


@router.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.whatsapp_enabled:
        raise AppError("CHANNEL_DISABLED", "WhatsApp no está activo.", 404)
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    signature = request.headers.get("X-Twilio-Signature", "")
    url = settings.twilio_webhook_public_url or str(request.url)
    if not verify_twilio_signature(url, params, signature):
        raise AppError("INVALID_SIGNATURE", "Firma de Twilio inválida.", 403)

    if (
        settings.messaging_mode == "twilio"
        and settings.twilio_account_sid
        and params.get("AccountSid") != settings.twilio_account_sid
    ):
        raise AppError("INVALID_ACCOUNT", "Cuenta de Twilio no autorizada.", 403)

    if settings.messaging_mode == "twilio" and params.get("To") != settings.twilio_whatsapp_from:
        raise AppError("INVALID_RECIPIENT", "Destinatario no autorizado.", 403)
    sid = params.get("MessageSid")
    if not sid:
        raise AppError("INVALID_PAYLOAD", "Falta MessageSid.", 422)

    try:
        event, duplicate = messaging_service.persist_inbound(
            db,
            provider="twilio",
            event_id=sid,
            payload=params,
        )
    except SQLAlchemyError:
        return Response(status_code=503, content="Retry later")

    if duplicate:
        return Response(content="<Response/>", media_type="application/xml", status_code=200)

    if settings.process_inbox_inline:
        messaging_service.process_inbound(db, event)
        messaging_service.deliver_pending(db)

    return Response(content="<Response/>", media_type="application/xml", status_code=200)


@router.post("/webhooks/telegram")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.telegram_enabled:
        raise AppError("CHANNEL_DISABLED", "Telegram no está activo.", 404)
    if not verify_telegram_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")):
        raise AppError("INVALID_SIGNATURE", "Token secreto de Telegram inválido.", 403)
    try:
        update = await request.json()
    except ValueError as exc:
        raise AppError("INVALID_PAYLOAD", "JSON inválido.", 422) from exc
    if not isinstance(update, dict) or "update_id" not in update:
        raise AppError("INVALID_PAYLOAD", "Falta update_id.", 422)

    try:
        event, duplicate = messaging_service.persist_inbound(
            db,
            provider="telegram",
            event_id=str(update["update_id"]),
            payload=update,
        )
    except SQLAlchemyError:
        return Response(status_code=503, content="Retry later")

    if not duplicate and settings.process_inbox_inline:
        messaging_service.process_inbound(db, event)
        messaging_service.deliver_pending(db)
    return Response(status_code=200)


@router.post("/webhooks/twilio/status")
async def twilio_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    signature = request.headers.get("X-Twilio-Signature", "")
    url = settings.twilio_status_public_url or str(request.url)
    if not verify_twilio_signature(url, params, signature):
        raise AppError("INVALID_SIGNATURE", "Firma de Twilio inválida.", 403)

    if (
        settings.messaging_mode == "twilio"
        and params.get("AccountSid") != settings.twilio_account_sid
    ):
        raise AppError("INVALID_ACCOUNT", "Cuenta no autorizada.", 403)

    sid = params.get("MessageSid")
    status = (params.get("MessageStatus") or params.get("SmsStatus") or "").upper()
    if not sid or not status:
        raise AppError("INVALID_PAYLOAD", "Faltan MessageSid o estado.", 422)

    messaging_service.record_delivery_event(
        db,
        provider_sid=sid,
        status=status,
        payload_hash=_payload_hash(params),
        provider_time=utcnow(),
    )
    return Response(status_code=200)
