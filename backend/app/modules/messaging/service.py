"""Inbox/outbox durable y comandos del agente por WhatsApp o Telegram (P0).

El webhook solo valida y persiste el evento antes de responder 2xx. El
procesamiento puede ocurrir en línea (demo) o en el worker, siempre desde la
tabla `inbound_events`. La entrega se registra en `outbound_messages`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decrypt_phone, normalize_phone
from app.db.base import utcnow
from app.integrations import telegram_gateway, twilio_gateway
from app.modules.audit.service import record as audit_record
from app.modules.business.models import Business
from app.modules.classification import service as classification_service
from app.modules.consents import service as consent_service
from app.modules.consents.models import Preference
from app.modules.identity import service as identity_service
from app.modules.identity.models import ChannelLink
from app.modules.insights import service as insights_service
from app.modules.ledger import domain as ledger_domain
from app.modules.ledger import service as ledger_service
from app.modules.messaging.models import DeliveryEvent, InboundEvent, OutboundMessage
from app.shared.clock import parse_datetime
from app.shared.money import Money

settings = get_settings()
logger = logging.getLogger("mica.messaging")

BACKOFF_SECONDS = [5, 30, 120, 600, 1800]
MAX_ATTEMPTS = len(BACKOFF_SECONDS)

STATUS_RANK = {
    "PENDING": 0,
    "SENDING": 1,
    "UNKNOWN": 1,
    "ACCEPTED": 2,
    "DELIVERED": 3,
    "FAILED": 3,
    "BLOCKED": 3,
    "CANCELLED": 3,
}

HELP_TEXT = (
    "Comandos de Mi Negocio:\n"
    "RESUMEN — ver tu semana\n"
    "PAUSAR / REANUDAR — activar o pausar reportes\n"
    "1 o 2 — aclarar un movimiento pendiente\n"
    "VINCULAR <código> — vincular este WhatsApp\n"
    "AYUDA — mostrar este mensaje"
)

CHANNEL_NAMES = {"twilio": "WhatsApp", "telegram": "Telegram"}


def channel_name(provider: str) -> str:
    return CHANNEL_NAMES.get(provider, "WhatsApp")


def channel_enabled(provider: str) -> bool:
    if provider == "telegram":
        return settings.telegram_enabled
    if provider == "twilio":
        return settings.whatsapp_enabled
    return False


def enabled_providers() -> list[str]:
    """Canales activos, en orden de preferencia para mensajes proactivos."""
    return [p for p in ("twilio", "telegram") if channel_enabled(p)]


def help_text(provider: str) -> str:
    if provider == "telegram":
        return (
            "Comandos de Mi Negocio:\n"
            "/resumen — ver tu semana\n"
            "/pausar · /reanudar — activar o pausar reportes\n"
            "1 o 2 — aclarar un movimiento pendiente\n"
            "/ayuda — mostrar este mensaje\n"
            "Para vincular, toca «Conectar con Telegram» en la app."
        )
    return HELP_TEXT


def _is_simulated(provider: str) -> bool:
    if provider == "telegram":
        return not telegram_gateway.is_live()
    return settings.messaging_mode != "twilio"


def _hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _backoff(attempt: int) -> datetime:
    seconds = BACKOFF_SECONDS[min(max(attempt - 1, 0), MAX_ATTEMPTS - 1)]
    return utcnow() + timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------


def persist_inbound(
    db: Session,
    *,
    provider: str,
    event_id: str,
    payload: dict,
    business_id: uuid.UUID | None = None,
    environment: str = "DEMO",
    commit: bool = True,
) -> tuple[InboundEvent, bool]:
    """Persiste el evento antes de responder 2xx. Devuelve (evento, duplicado)."""
    digest = _hash(payload)
    existing = db.scalar(
        select(InboundEvent).where(
            InboundEvent.provider == provider,
            InboundEvent.environment == environment,
            InboundEvent.event_id == event_id,
        )
    )
    if existing is not None:
        if existing.payload_hash != digest:
            raise AppError(
                "INBOUND_CONFLICT",
                "El mismo event_id llegó con un payload diferente.",
                409,
            )
        return existing, True

    event = InboundEvent(
        provider=provider,
        environment=environment,
        event_id=event_id,
        business_id=business_id,
        payload_json=payload,
        payload_hash=digest,
        status="PENDING",
        received_at=utcnow(),
    )
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        existing = db.scalars(
            select(InboundEvent).where(
                InboundEvent.provider == provider,
                InboundEvent.environment == environment,
                InboundEvent.event_id == event_id,
            )
        ).one()
        if existing.payload_hash != digest:
            raise AppError(
                "INBOUND_CONFLICT", "Evento duplicado con otro contenido.", 409
            ) from None
        return existing, True
    if commit:
        db.commit()
        db.refresh(event)
    else:
        db.flush()
    return event, False


def _fail_event(db: Session, event: InboundEvent, code: str) -> None:
    event.error_code = code
    if event.attempts >= MAX_ATTEMPTS:
        event.status = "DEAD"
        event.next_attempt_at = None
    else:
        event.status = "RETRY"
        event.next_attempt_at = _backoff(event.attempts)
    event.locked_until = None
    db.commit()


def process_inbound(db: Session, event: InboundEvent) -> InboundEvent:
    event = db.scalars(
        select(InboundEvent)
        .where(InboundEvent.id == event.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    if event.status == "DONE":
        return event
    if event.status == "PROCESSING" and event.locked_until and event.locked_until > utcnow():
        return event

    event.status = "PROCESSING"
    event.attempts += 1
    event.locked_until = utcnow() + timedelta(minutes=2)
    db.commit()

    try:
        event = db.scalars(
            select(InboundEvent).where(InboundEvent.id == event.id).with_for_update()
        ).one()
        if event.provider == "simulator":
            _handle_simulator(db, event)
        elif event.provider == "twilio":
            _handle_twilio(db, event)
        elif event.provider == "telegram":
            _handle_telegram(db, event)
        else:
            raise AppError("UNKNOWN_PROVIDER", "Proveedor de evento no soportado.", 422)

        event.status = "DONE"
        event.processed_at = utcnow()
        event.error_code = None
        event.next_attempt_at = None
        event.locked_until = None
        db.commit()
    except AppError as exc:
        db.rollback()
        current = db.get(InboundEvent, event.id)
        if current is not None:
            _fail_event(db, current, exc.code)
    except Exception:
        db.rollback()
        current = db.get(InboundEvent, event.id)
        if current is not None:
            _fail_event(db, current, "PROCESSING_ERROR")
    return event


_telegram_offset: int | None = None


def poll_telegram(db: Session) -> int:
    """Trae mensajes nuevos con getUpdates y los guarda en el inbox.

    Solo corre con Telegram activo, token configurado y TELEGRAM_POLLING=true.
    Los repetidos se descartan por update_id (idempotencia del inbox).
    """
    global _telegram_offset
    if not (settings.telegram_enabled and settings.telegram_polling and telegram_gateway.is_live()):
        return 0
    try:
        updates = telegram_gateway.get_updates(_telegram_offset)
    except Exception as exc:  # red caída o token inválido: se reintenta en el próximo ciclo
        logger.warning("telegram.poll_failed type=%s", type(exc).__name__)
        return 0
    for update in updates:
        persist_inbound(
            db,
            provider="telegram",
            event_id=str(update["update_id"]),
            payload=update,
        )
        _telegram_offset = int(update["update_id"]) + 1
    return len(updates)


def process_pending_inbound(db: Session, limit: int = 20) -> int:
    now = utcnow()
    events = list(
        db.scalars(
            select(InboundEvent)
            .where(
                InboundEvent.status.in_(["PENDING", "RETRY", "PROCESSING"]),
                or_(InboundEvent.next_attempt_at.is_(None), InboundEvent.next_attempt_at <= now),
                or_(InboundEvent.locked_until.is_(None), InboundEvent.locked_until < now),
            )
            .order_by(InboundEvent.received_at.asc())
            .limit(limit)
        )
    )
    for event in events:
        process_inbound(db, event)
    return len(events)


# ---------------------------------------------------------------------------
# Simulador de cobros
# ---------------------------------------------------------------------------


def _handle_simulator(db: Session, event: InboundEvent) -> None:
    payload = event.payload_json or {}
    if payload.get("event_type") != "transaction.confirmed":
        raise AppError("INVALID_EVENT_TYPE", "Tipo de evento no soportado.", 422)
    if payload.get("environment", "DEMO") != "DEMO":
        raise AppError("INVALID_ENVIRONMENT", "Solo se admite DEMO.", 422)

    currency = payload.get("currency", "PEN")
    if currency != "PEN":
        raise AppError("INVALID_CURRENCY", "Solo se admite PEN.", 422)

    reference = payload.get("business_reference")
    try:
        business_id = uuid.UUID(str(reference))
    except (ValueError, TypeError) as exc:
        raise AppError("INVALID_BUSINESS_REFERENCE", "Negocio inválido.", 422) from exc

    business = db.get(Business, business_id)
    if business is None:
        raise AppError("BUSINESS_NOT_FOUND", "Negocio no encontrado.", 404)
    if business.status != "ACTIVE":
        raise AppError("BUSINESS_NOT_ACTIVE", "El negocio no está activo.", 409)

    money = Money.parse(payload.get("amount"), currency)
    occurred_at = parse_datetime(payload.get("occurred_at"), default=event.received_at)
    external_id = str(payload.get("external_transaction_id") or "")
    if not external_id:
        raise AppError("INVALID_PAYLOAD", "Falta external_transaction_id.", 422)

    kind = payload.get("kind")
    if kind == "SALE":
        ledger_service.post(
            db,
            business_id=business.id,
            kind=ledger_domain.SALE,
            amount=money.amount,
            medium=ledger_domain.DIGITAL,
            source=ledger_domain.SIMULATED,
            environment="DEMO",
            occurred_at=occurred_at,
            provider="simulator",
            external_transaction_id=external_id,
            inbound_event_id=event.id,
            description="Cobro por QR demo",
            commit=False,
        )
    elif kind == "REVERSAL":
        original_external = payload.get("original_external_transaction_id")
        if not original_external:
            raise AppError("INVALID_PAYLOAD", "Falta original_external_transaction_id.", 422)
        original = ledger_service.find_by_external(db, "simulator", "DEMO", str(original_external))
        if original is None:
            raise AppError(
                "ORIGINAL_NOT_FOUND",
                "La reversión espera a su operación original para conciliar.",
                409,
            )
        if original.business_id != business.id or original.amount != money.amount:
            raise AppError(
                "REVERSAL_CONFLICT",
                "La reversión no corresponde al negocio o importe original.",
                409,
            )
        ledger_service.post_reversal(
            db,
            original,
            reason="Reversión recibida por el simulador",
            commit=False,
        )
    else:
        raise AppError("INVALID_KIND", "Solo SALE o REVERSAL en P0.", 422)

    event.business_id = business.id
    db.flush()


# ---------------------------------------------------------------------------
# Comandos del agente (WhatsApp y Telegram comparten la misma lógica)
# ---------------------------------------------------------------------------


def _preferences(db: Session, business_id: uuid.UUID) -> Preference:
    prefs = db.get(Preference, business_id)
    if prefs is None:
        prefs = Preference(business_id=business_id)
        db.add(prefs)
        db.flush()
    return prefs


def enqueue_outbound(
    db: Session,
    *,
    business_id: uuid.UUID,
    channel_link_id: uuid.UUID,
    body: str,
    dedupe_key: str,
    report_id: uuid.UUID | None = None,
    commit: bool = False,
) -> OutboundMessage:
    existing = db.scalar(select(OutboundMessage).where(OutboundMessage.dedupe_key == dedupe_key))
    if existing is not None:
        return existing

    message = OutboundMessage(
        business_id=business_id,
        report_id=report_id,
        channel_link_id=channel_link_id,
        dedupe_key=dedupe_key,
        body=body,
        status="PENDING",
    )
    db.add(message)
    db.flush()
    if commit:
        db.commit()
        db.refresh(message)
    return message


def _reply(
    db: Session,
    business: Business,
    link: ChannelLink,
    event: InboundEvent,
    body: str,
    *,
    report_id: uuid.UUID | None = None,
) -> OutboundMessage:
    message = enqueue_outbound(
        db,
        business_id=business.id,
        channel_link_id=link.id,
        body=body,
        dedupe_key=f"reply:{event.event_id}",
        report_id=report_id,
    )
    audit_record(
        db,
        business.id,
        "MESSAGE_QUEUED",
        "outbound_message",
        message.id,
        actor_type="SYSTEM",
        metadata={"channel": link.provider, "simulated": _is_simulated(link.provider)},
    )
    return message


def _handle_twilio(db: Session, event: InboundEvent) -> None:
    payload = event.payload_json or {}
    raw_from = str(payload.get("From") or "")
    body = str(payload.get("Body") or "").strip()
    if not raw_from:
        raise AppError("INVALID_PAYLOAD", "Falta el remitente.", 422)

    try:
        phone = normalize_phone(raw_from)
    except ValueError as exc:
        raise AppError("INVALID_PHONE", "Teléfono inválido.", 422) from exc

    command, _, argument = body.partition(" ")
    _handle_command(db, event, "twilio", phone, command.upper().strip(), argument.strip())


def parse_telegram_text(text: str) -> tuple[str, str]:
    """Convierte '/start CODIGO', '/resumen@MicaBot' o 'resumen' en (COMANDO, argumento)."""
    command, _, argument = text.strip().partition(" ")
    command = command.removeprefix("/").split("@", 1)[0].upper().strip()
    argument = argument.strip()
    if command == "START":
        command = "VINCULAR" if argument else "AYUDA"
    return command, argument


def _handle_telegram(db: Session, event: InboundEvent) -> None:
    payload = event.payload_json or {}
    message = payload.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    if not chat_id or chat.get("type", "private") != "private":
        return  # sin mensaje o chat grupal: el agente solo atiende chats privados
    command, argument = parse_telegram_text(str(message.get("text") or ""))
    _handle_command(db, event, "telegram", chat_id, command, argument)


def _handle_command(
    db: Session,
    event: InboundEvent,
    provider: str,
    phone: str,
    command: str,
    argument: str,
) -> None:
    """``phone`` es la dirección del canal: teléfono (WhatsApp) o chat_id (Telegram)."""
    name = channel_name(provider)

    business: Business | None
    link: ChannelLink | None
    if command == "VINCULAR":
        if not argument:
            raise AppError("LINK_CODE_REQUIRED", "Envía VINCULAR <código>.", 422)
        try:
            business, link = identity_service.consume_link_challenge(
                db, argument, phone, provider, commit=False
            )
        except AppError as exc:
            if exc.code != "LINK_CODE_USED":
                raise
            link = identity_service.find_link_by_phone(
                db,
                phone,
                provider,
                business_id=event.business_id,
                environment=event.environment,
            )
            if link is None:
                raise
            business = db.get(Business, link.business_id)
            if business is None:
                raise AppError("BUSINESS_NOT_FOUND", "Negocio no encontrado.", 404) from exc
        event.business_id = business.id
        _reply(
            db,
            business,
            link,
            event,
            f"Tu {name} quedó vinculado a Mi Negocio. Envía AYUDA para ver los comandos.",
        )
        return

    link = identity_service.find_link_by_phone(
        db,
        phone,
        provider,
        business_id=event.business_id,
        environment=event.environment,
    )
    if link is None:
        audit_record(
            db,
            None,
            "INBOUND_UNLINKED",
            "inbound_event",
            event.id,
            actor_type="SYSTEM",
            metadata={"provider": provider},
        )
        return

    business = db.get(Business, link.business_id)
    if business is None:
        raise AppError("BUSINESS_NOT_FOUND", "Negocio no encontrado.", 404)

    event.business_id = business.id
    link.last_inbound_at = utcnow()

    if command == "AYUDA":
        _reply(db, business, link, event, help_text(provider))
        return

    if command == "PAUSAR":
        prefs = _preferences(db, business.id)
        prefs.reports_enabled = False
        cancel_pending_for_business(db, business.id, "REPORTS_PAUSED")
        _reply(
            db,
            business,
            link,
            event,
            f"Reportes por {name} pausados. Tus movimientos y saldos siguen disponibles en la app.",
        )
        return

    if command == "REANUDAR":
        if not consent_service.has_active(db, business.id, "WHATSAPP_REPORTS"):
            _reply(
                db,
                business,
                link,
                event,
                f"No tienes consentimiento activo para reportes por {name}. Actívalo en la app.",
            )
            return
        prefs = _preferences(db, business.id)
        prefs.reports_enabled = True
        _reply(
            db,
            business,
            link,
            event,
            f"Reportes por {name} activados. Envía RESUMEN cuando quieras ver tu semana.",
        )
        return

    if command == "RESUMEN":
        if not consent_service.has_active(db, business.id, "WHATSAPP_REPORTS"):
            _reply(
                db,
                business,
                link,
                event,
                f"El envío de reportes por {name} no está autorizado. Puedes activarlo en la app.",
            )
            return
        if not _preferences(db, business.id).reports_enabled:
            _reply(
                db,
                business,
                link,
                event,
                "Tus reportes están pausados. Envía REANUDAR para activarlos.",
            )
            return
        report = insights_service.generate_report(
            db, business, cutoff_at=event.received_at, commit=False
        )
        _reply(db, business, link, event, report.text, report_id=report.id)
        return

    if command in ("1", "2"):
        request = classification_service.open_for_business(db, business.id)
        if request is None:
            _reply(
                db,
                business,
                link,
                event,
                "No tienes movimientos pendientes de clasificar. Envía AYUDA para ver los comandos.",
            )
            return
        option = "BUSINESS_PAYMENT" if command == "1" else "HOUSEHOLD_WITHDRAWAL"
        try:
            classification_service.resolve(
                db,
                business_id=business.id,
                request_id=request.id,
                option=option,
                expected_version=request.version,
                commit=False,
            )
        except AppError as exc:
            if exc.code not in (
                "CLASSIFICATION_ALREADY_RESOLVED",
                "CLASSIFICATION_VERSION_CONFLICT",
            ):
                raise
        _reply(
            db,
            business,
            link,
            event,
            "Gracias. Actualizamos la clasificación de tu movimiento. Tu resumen semanal "
            "se recalculará con la nueva categoría.",
        )
        return

    _reply(db, business, link, event, help_text(provider))


# ---------------------------------------------------------------------------
# Outbox y entrega
# ---------------------------------------------------------------------------


def _can_send(db: Session, message: OutboundMessage) -> bool:
    link = db.get(ChannelLink, message.channel_link_id)
    if link is None or link.status != "ACTIVE":
        return False
    business = db.get(Business, message.business_id)
    if business is None or link.business_id != message.business_id:
        return False
    if message.report_id is not None:
        if business.status != "ACTIVE":
            return False
        if not consent_service.has_active(db, business.id, "WHATSAPP_REPORTS"):
            return False
        prefs = db.get(Preference, business.id)
        if prefs is not None and not prefs.reports_enabled:
            return False
    return True


def deliver_message(db: Session, message: OutboundMessage) -> OutboundMessage:
    current_message = db.scalar(
        select(OutboundMessage)
        .where(OutboundMessage.id == message.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if current_message is None:
        raise AppError("MESSAGE_NOT_FOUND", "Mensaje inexistente.", 404)
    message = current_message
    if message.status in ("DELIVERED", "ACCEPTED", "CANCELLED", "BLOCKED", "FAILED", "UNKNOWN"):
        return message
    if message.status == "SENDING":
        if message.locked_until is not None and message.locked_until > utcnow():
            return message
        message.status = "UNKNOWN"
        message.error_code = "SEND_INTERRUPTED"
        message.locked_until = None
        db.commit()
        return message

    if not _can_send(db, message):
        message.status = "BLOCKED"
        message.error_code = "CONSENT_OR_LINK_INACTIVE"
        message.locked_until = None
        db.commit()
        return message

    link = db.get(ChannelLink, message.channel_link_id)
    if link is None:
        raise AppError("CHANNEL_NOT_LINKED", "Canal no vinculado.", 409)
    # Un canal apagado no envía nada real; el modo simulado no contacta a nadie.
    if not channel_enabled(link.provider) and not _is_simulated(link.provider):
        message.status = "BLOCKED"
        message.error_code = "CHANNEL_DISABLED"
        message.locked_until = None
        db.commit()
        return message
    if (
        link.provider == "twilio"
        and settings.messaging_mode == "twilio"
        and (link.last_inbound_at is None or utcnow() - link.last_inbound_at >= timedelta(hours=24))
    ):
        message.status = "BLOCKED"
        message.error_code = "OUTSIDE_SESSION_WINDOW"
        db.commit()
        return message
    address = decrypt_phone(link.phone_encrypted)
    gateway = telegram_gateway if link.provider == "telegram" else twilio_gateway

    message.status = "SENDING"
    message.attempts += 1
    message.locked_until = utcnow() + timedelta(minutes=2)
    db.commit()

    try:
        result = gateway.send_text(address, message.body)
        message = cast(OutboundMessage, db.get(OutboundMessage, message.id))
        message.provider_sid = result.provider_sid
        message.status = result.status if result.status in STATUS_RANK else "ACCEPTED"
        message.accepted_at = utcnow()
        if message.status == "DELIVERED":
            message.delivered_at = utcnow()
        message.error_code = None
        message.locked_until = None
        db.commit()
    except Exception:
        db.rollback()
        message = cast(OutboundMessage, db.get(OutboundMessage, message.id))
        message.error_code = "SEND_RESULT_UNKNOWN"
        message.locked_until = None
        message.status = "UNKNOWN"
        message.next_attempt_at = None
        db.commit()
    return message


def deliver_pending(db: Session, limit: int = 20) -> int:
    now = utcnow()
    messages = list(
        db.scalars(
            select(OutboundMessage)
            .where(
                OutboundMessage.status.in_(["PENDING", "RETRY", "SENDING"]),
                or_(
                    OutboundMessage.next_attempt_at.is_(None),
                    OutboundMessage.next_attempt_at <= now,
                ),
                or_(
                    OutboundMessage.locked_until.is_(None),
                    OutboundMessage.locked_until < now,
                ),
            )
            .order_by(OutboundMessage.created_at.asc())
            .limit(limit)
        )
    )
    for message in messages:
        deliver_message(db, message)
    return len(messages)


def cancel_pending_for_business(db: Session, business_id: uuid.UUID, reason: str) -> int:
    messages = list(
        db.scalars(
            select(OutboundMessage).where(
                OutboundMessage.business_id == business_id,
                OutboundMessage.status.in_(["PENDING", "RETRY", "SENDING"]),
            )
        )
    )
    for message in messages:
        message.status = "CANCELLED"
        message.error_code = reason
        message.locked_until = None
    db.flush()
    return len(messages)


def record_delivery_event(
    db: Session,
    *,
    provider_sid: str,
    status: str,
    payload_hash: str,
    provider_time: datetime | None = None,
    commit: bool = True,
) -> DeliveryEvent | None:
    message = db.scalar(select(OutboundMessage).where(OutboundMessage.provider_sid == provider_sid))
    if message is None:
        return None

    existing = db.scalar(
        select(DeliveryEvent).where(
            DeliveryEvent.provider_sid == provider_sid,
            DeliveryEvent.status == status,
            DeliveryEvent.payload_hash == payload_hash,
        )
    )
    if existing is not None:
        return existing

    event = DeliveryEvent(
        message_id=message.id,
        provider_sid=provider_sid,
        status=status,
        provider_time=provider_time,
        payload_hash=payload_hash,
    )
    db.add(event)

    delivery_status = {
        "SENT": "ACCEPTED",
        "QUEUED": "ACCEPTED",
        "SENDING": "ACCEPTED",
        "READ": "DELIVERED",
        "UNDELIVERED": "FAILED",
    }.get(status, status)
    if (
        delivery_status in STATUS_RANK
        and message.status not in ("DELIVERED", "FAILED", "CANCELLED", "BLOCKED")
        and STATUS_RANK[delivery_status] >= STATUS_RANK.get(message.status, 0)
    ):
        message.status = delivery_status
        if delivery_status == "ACCEPTED":
            message.accepted_at = provider_time or utcnow()
        if delivery_status == "DELIVERED":
            message.delivered_at = provider_time or utcnow()
    message.locked_until = None
    db.flush()
    if commit:
        db.commit()
        db.refresh(event)
    return event


def message_to_dict(message: OutboundMessage) -> dict:
    return {
        "id": str(message.id),
        "status": message.status,
        "provider_sid": message.provider_sid,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
        "accepted_at": message.accepted_at.isoformat() if message.accepted_at else None,
        "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
    }
