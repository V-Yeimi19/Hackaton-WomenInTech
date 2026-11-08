"""Audio de Telegram: perfil compartido, historial, deduplicación y errores."""

import copy
import random

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations import audio_gateway, llm_gateway, telegram_gateway
from app.modules.messaging import service as messaging
from app.modules.messaging.models import InboundEvent, OutboundMessage
from tests.integration.test_http_flow import client, session  # noqa: F401
from tests.integration.test_telegram_flow import _linked_chat, _send, _update

pytestmark = pytest.mark.integration
settings = get_settings()


def audio_update(chat_id, kind="voice", **overrides):
    update = _update(chat_id, "")
    del update["message"]["text"]
    update["message"][kind] = {
        "file_id": "test-audio-id",
        "duration": 6,
        "file_size": 1200,
        "mime_type": "audio/ogg",
        **overrides,
    }
    return update


def process(client, pg_engine, update):  # noqa: F811
    response = client.post("/api/v1/webhooks/telegram", json=update)
    assert response.status_code == 200, response.text
    with Session(pg_engine) as db:
        event = db.scalars(
            select(InboundEvent).where(
                InboundEvent.provider == "telegram",
                InboundEvent.event_id == str(update["update_id"]),
            )
        ).one()
        messaging.process_inbound(db, event)
        assert event.status == "DONE", event.error_code
        messaging.deliver_pending(db)
        reply = db.scalar(
            select(OutboundMessage).where(
                OutboundMessage.dedupe_key == f"reply:{update['update_id']}",
            )
        )
        assert event.payload_json == update  # conservar el original y su hash
        return reply.body if reply else None, event.transcript


def test_voice_uses_shared_profile_and_preserves_transcript_in_telegram_history(
    client,  # noqa: F811
    pg_engine,
    monkeypatch,
):
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "whatsapp_enabled", False)
    headers = session(client, "risk")
    wallet = next(
        item
        for item in client.get("/api/v1/wallets", headers=headers).json()["items"]
        if item["role"] == "BUSINESS"
    )
    assert (
        client.patch(
            "/api/v1/agent/profile",
            headers=headers,
            json={
                "wallet_id": wallet["id"],
                "answers": ["Cafetería", "Café y panes"],
                "expected_version": 0,
            },
        ).status_code
        == 200
    )
    code = client.post("/api/v1/channel-link-challenges", headers=headers).json()["code"]
    chat_id = random.randint(10**9, 10**10)
    _send(client, pg_engine, chat_id, f"/start {code}")
    calls, contexts = [], []
    monkeypatch.setattr(audio_gateway, "is_enabled", lambda: True)
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_model", "test-model")
    monkeypatch.setattr(
        telegram_gateway, "download_audio", lambda file_id: (b"test-audio", "audio.ogg")
    )

    def transcribe(content, filename):
        calls.append((content, filename))
        return "¿Cómo puedo vender más café?"

    def chat(messages):
        contexts.append(copy.deepcopy(messages))
        return "Revisa cuáles son tus productos más pedidos."

    monkeypatch.setattr(audio_gateway, "transcribe", transcribe)
    monkeypatch.setattr(llm_gateway, "chat", chat)
    update = audio_update(chat_id)
    reply, transcript = process(client, pg_engine, update)
    assert reply == "Revisa cuáles son tus productos más pedidos."
    assert transcript == "¿Cómo puedo vender más café?"
    assert contexts[-1][-1] == {"role": "user", "content": transcript}
    assert "Cafetería" in str(contexts[-1])
    assert "Café y panes" in str(contexts[-1])
    assert process(client, pg_engine, update) == (reply, transcript)
    assert len(calls) == 1 and len(contexts) == 1
    _send(client, pg_engine, chat_id, "¿Y qué más me recomiendas?")
    assert {"role": "user", "content": transcript} in contexts[-1]
    # El audio no aparece como conversación de la app.
    assert (
        client.get(f"/api/v1/agent/chat?wallet_id={wallet['id']}", headers=headers).json()["items"]
        == []
    )
    with Session(pg_engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(OutboundMessage)
                .where(
                    OutboundMessage.dedupe_key == f"reply:{update['update_id']}",
                )
            )
            == 1
        )


@pytest.mark.parametrize("kind", ["voice", "audio", "document"])
def test_transcribed_options_work_in_supported_telegram_audio_types(
    client,  # noqa: F811
    pg_engine,
    monkeypatch,
    kind,
):
    chat_id = _linked_chat(client, pg_engine, monkeypatch)
    monkeypatch.setattr(audio_gateway, "is_enabled", lambda: True)
    monkeypatch.setattr(telegram_gateway, "download_audio", lambda file_id: (b"audio", "audio.ogg"))
    monkeypatch.setattr(audio_gateway, "transcribe", lambda *args: "aYuDa.")
    reply, transcript = process(client, pg_engine, audio_update(chat_id, kind))
    assert "Escríbeme una de estas opciones" in reply
    assert transcript == "aYuDa."


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"duration": 181}, "muy largo"),
        ({"file_size": 10_000_001}, "muy pesado"),
    ],
)
def test_audio_limits_reply_without_downloading(
    client,  # noqa: F811
    pg_engine,
    monkeypatch,
    overrides,
    expected,
):
    chat_id = _linked_chat(client, pg_engine, monkeypatch)
    monkeypatch.setattr(audio_gateway, "is_enabled", lambda: True)
    monkeypatch.setattr(
        telegram_gateway,
        "download_audio",
        lambda *args: pytest.fail("Must reject before downloading"),
    )
    reply, transcript = process(client, pg_engine, audio_update(chat_id, **overrides))
    assert expected in reply
    assert transcript is None


def test_transcription_failure_replies_instead_of_retrying_forever(client, pg_engine, monkeypatch):  # noqa: F811
    chat_id = _linked_chat(client, pg_engine, monkeypatch)
    monkeypatch.setattr(audio_gateway, "is_enabled", lambda: True)
    monkeypatch.setattr(telegram_gateway, "download_audio", lambda file_id: (b"audio", "audio.ogg"))

    def fail(*args):
        raise audio_gateway.AudioError("No pude transcribir tu audio. Escríbeme tu consulta.")

    monkeypatch.setattr(audio_gateway, "transcribe", fail)
    reply, transcript = process(client, pg_engine, audio_update(chat_id))
    assert "No pude transcribir" in reply
    assert transcript is None


def test_unlinked_audio_never_downloads_or_transcribes(client, pg_engine, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(
        telegram_gateway,
        "download_audio",
        lambda *a: pytest.fail("Unlinked chat must not download"),
    )
    assert process(client, pg_engine, audio_update(random.randint(10**9, 10**10))) == (None, None)


def test_disabled_audio_has_actionable_reply(client, pg_engine, monkeypatch):  # noqa: F811
    chat_id = _linked_chat(client, pg_engine, monkeypatch)
    monkeypatch.setattr(audio_gateway, "is_enabled", lambda: False)
    monkeypatch.setattr(
        telegram_gateway,
        "download_audio",
        lambda *a: pytest.fail("Disabled audio must not download"),
    )
    reply, transcript = process(client, pg_engine, audio_update(chat_id))
    assert "Escríbeme tu consulta" in reply
    assert transcript is None
