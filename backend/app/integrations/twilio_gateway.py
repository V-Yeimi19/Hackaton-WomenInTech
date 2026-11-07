"""Puerta de salida de mensajería.

``fake`` no contacta a ninguna persona: genera un SID local y marca la entrega
como simulada. ``twilio`` usa el SDK oficial y deja el estado en ``ACCEPTED``
hasta que llegue un callback de estado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()


@dataclass
class SendResult:
    provider_sid: str
    status: str
    simulated: bool


def _fake_send() -> SendResult:
    return SendResult(
        provider_sid=f"SMDEMO{uuid.uuid4().hex[:24]}", status="DELIVERED", simulated=True
    )


def send_text(to_phone: str, body: str) -> SendResult:
    if settings.messaging_mode != "twilio":
        return _fake_send()

    from twilio.rest import Client  # import diferido: no requerido en modo fake

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        from_=settings.twilio_whatsapp_from,
        to="whatsapp:" + to_phone.removeprefix("whatsapp:"),
        body=body,
        status_callback=settings.twilio_status_public_url or None,
    )
    return SendResult(provider_sid=message.sid, status="ACCEPTED", simulated=False)


def send_template(to_phone: str, content_sid: str, variables: dict | None = None) -> SendResult:
    if settings.messaging_mode != "twilio":
        return _fake_send()

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        from_=settings.twilio_whatsapp_from,
        to="whatsapp:" + to_phone.removeprefix("whatsapp:"),
        content_sid=content_sid,
        content_variables=variables or {},
    )
    return SendResult(provider_sid=message.sid, status="ACCEPTED", simulated=False)
