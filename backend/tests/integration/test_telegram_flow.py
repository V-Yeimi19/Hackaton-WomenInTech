"""Canal Telegram: vínculo con /start, comandos y selección de canal por variables."""

import random

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import channel_lookup_hash
from app.modules.identity.models import ChannelLink
from app.modules.messaging import service as messaging
from app.modules.messaging.models import OutboundMessage
from tests.integration.test_http_flow import client, session  # noqa: F401

pytestmark = pytest.mark.integration
settings = get_settings()


def _update(chat_id: int, text: str) -> dict:
    return {
        "update_id": random.randint(10**8, 10**9),
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "Prueba"},
            "text": text,
        },
    }


def _send(client, pg_engine, chat_id: int, text: str) -> list[str]:  # noqa: F811
    response = client.post("/api/v1/webhooks/telegram", json=_update(chat_id, text))
    assert response.status_code == 200, response.text
    with Session(pg_engine) as db:
        messaging.process_pending_inbound(db)
        messaging.deliver_pending(db)
        link = db.scalar(
            select(ChannelLink).where(
                ChannelLink.provider == "telegram",
                ChannelLink.phone_lookup_hash == channel_lookup_hash("telegram", str(chat_id)),
            )
        )
        if link is None:
            return []
        rows = db.scalars(
            select(OutboundMessage)
            .where(OutboundMessage.channel_link_id == link.id)
            .order_by(OutboundMessage.created_at.asc())
        )
        return [f"{m.status}|{m.body}" for m in rows]


def test_telegram_link_and_commands(client, pg_engine, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "whatsapp_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_username", "MicaPruebaBot")
    headers = session(client, "risk")
    challenge = client.post("/api/v1/channel-link-challenges", headers=headers)
    assert challenge.status_code == 201, challenge.text
    body = challenge.json()
    assert body["channel"] == "telegram"
    assert body["telegram_url"] == f"https://t.me/MicaPruebaBot?start={body['code']}"

    me = client.get("/api/v1/me", headers=headers).json()["telegram"]
    assert me == {"enabled": True, "linked": False, "bot_url": "https://t.me/MicaPruebaBot"}

    chat_id = random.randint(10**9, 10**10)
    messages = _send(client, pg_engine, chat_id, f"/start {body['code']}")
    assert messages and "Tu Telegram quedó vinculado" in messages[-1]
    assert client.get("/api/v1/me", headers=headers).json()["telegram"]["linked"] is True
    assert messages[-1].startswith("DELIVERED|")  # simulado: sin token no sale nada real

    messages = _send(client, pg_engine, chat_id, "/resumen")
    assert "Tu semana en Mi Negocio" in messages[-1]

    messages = _send(client, pg_engine, chat_id, "/ayuda")
    assert "/resumen" in messages[-1] and "WhatsApp" not in messages[-1]


def test_unlinked_telegram_chat_gets_no_reply(client, pg_engine):  # noqa: F811
    assert _send(client, pg_engine, random.randint(10**9, 10**10), "/resumen") == []


def test_disabled_channels_reject_webhooks(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "whatsapp_enabled", False)
    response = client.post("/api/v1/webhooks/twilio/whatsapp", data={"MessageSid": "SMx"})
    assert response.status_code == 404
    monkeypatch.setattr(settings, "telegram_enabled", False)
    response = client.post("/api/v1/webhooks/telegram", json=_update(1, "/ayuda"))
    assert response.status_code == 404


def test_telegram_secret_is_required_with_real_token(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "123:fake")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "secreto-de-prueba")
    assert client.post("/api/v1/webhooks/telegram", json=_update(1, "/ayuda")).status_code == 403
    ok = client.post(
        "/api/v1/webhooks/telegram",
        json=_update(1, "/ayuda"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secreto-de-prueba"},
    )
    assert ok.status_code == 200
