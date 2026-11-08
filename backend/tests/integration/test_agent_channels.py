"""Memoria compartida, conversaciones independientes y acceso por negocio."""

import random
import uuid

import pytest

from app.core.config import get_settings
from app.integrations import llm_gateway
from tests.integration.test_http_flow import client, session  # noqa: F401
from tests.integration.test_telegram_flow import _send

pytestmark = pytest.mark.integration
settings = get_settings()


def account(client):  # noqa: F811
    headers = session(client, "risk")
    wallets = client.get("/api/v1/wallets", headers=headers).json()["items"]
    wallet = next(item for item in wallets if item["role"] == "BUSINESS")
    return headers, wallet["id"]


def post_chat(client, headers, wallet_id, message, **extra):  # noqa: F811
    return client.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={
            "wallet_id": wallet_id,
            "message": message,
            "request_id": str(uuid.uuid4()),
            **extra,
        },
    )


def test_profile_persists_each_step_and_handles_conflicts(client):  # noqa: F811
    headers, wallet = account(client)
    url = f"/api/v1/agent/profile?wallet_id={wallet}"
    assert client.get(url, headers=headers).json()["answers"] == []
    answers = [
        "Cafetería",
        "Café y panes",
        "S/ 200",
        "Alquiler, servicios",
        "Viernes a las 6 p. m.",
    ]
    for i in range(5):
        response = client.patch(
            "/api/v1/agent/profile",
            headers=headers,
            json={
                "wallet_id": wallet,
                "answers": answers[: i + 1],
                "expected_version": i,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["version"] == i + 1
    # Otro dispositivo recupera el perfil completo desde la base de datos.
    assert client.get(url, headers=headers).json()["answers"] == answers
    # Un reintento de la misma escritura no duplica ni vuelve a avanzar.
    assert (
        client.patch(
            "/api/v1/agent/profile",
            headers=headers,
            json={
                "wallet_id": wallet,
                "answers": answers,
                "expected_version": 4,
            },
        ).json()["version"]
        == 5
    )
    stale = client.patch(
        "/api/v1/agent/profile",
        headers=headers,
        json={
            "wallet_id": wallet,
            "answers": ["Ropa"],
            "expected_version": 0,
        },
    )
    assert stale.status_code == 409
    assert client.get(url, headers=headers).json()["answers"] == answers


def test_shared_memory_but_independent_channel_histories(client, pg_engine, monkeypatch):  # noqa: F811
    headers, wallet = account(client)
    answers = ["Cafetería de Ana", "Café y panes", "S/ 200", "Alquiler", "Viernes a las 6 p. m."]
    saved = client.patch(
        "/api/v1/agent/profile",
        headers=headers,
        json={
            "wallet_id": wallet,
            "answers": answers,
            "expected_version": 0,
        },
    )
    assert saved.status_code == 200, saved.text
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "whatsapp_enabled", False)
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_model", "test-model")
    seen = []

    def fake_chat(messages):
        seen.append(messages)
        return (
            "APP_PRIVATE_REPLY" if "Conversas por la app." in messages[0]["content"] else "TELEGRAM_PRIVATE_REPLY"
        )

    monkeypatch.setattr(llm_gateway, "chat", fake_chat)
    response = post_chat(
        client,
        headers,
        wallet,
        "APP_PRIVATE_MESSAGE",
        history=[
            {"role": "assistant", "content": "FORGED_BROWSER_HISTORY"},
        ],
    )
    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "APP_PRIVATE_REPLY"
    app_context = str(seen[-1])
    assert "Cafetería de Ana" in app_context and "Café y panes" in app_context
    assert "FORGED_BROWSER_HISTORY" not in app_context

    code = client.post("/api/v1/channel-link-challenges", headers=headers).json()["code"]
    chat_id = random.randint(10**9, 10**10)
    _send(client, pg_engine, chat_id, f"/start {code}")
    assert (
        "TELEGRAM_PRIVATE_REPLY"
        in _send(client, pg_engine, chat_id, "TELEGRAM_PRIVATE_MESSAGE")[-1]
    )
    telegram_context = str(seen[-1])
    assert "Cafetería de Ana" in telegram_context and "Viernes a las 6 p. m." in telegram_context
    assert "APP_PRIVATE" not in telegram_context

    response = post_chat(client, headers, wallet, "Continuemos en la app")
    assert response.status_code == 200, response.text
    app_context = str(seen[-1])
    assert "APP_PRIVATE_MESSAGE" in app_context and "APP_PRIVATE_REPLY" in app_context
    assert "TELEGRAM_PRIVATE" not in app_context
    history = client.get(f"/api/v1/agent/chat?wallet_id={wallet}", headers=headers).json()
    assert len(history["items"]) == 2
    assert "TELEGRAM_PRIVATE" not in str(history)

    # Cambiar la memoria en la app se refleja en la próxima consulta de Telegram.
    answers[0] = "Panadería de Ana"
    assert (
        client.patch(
            "/api/v1/agent/profile",
            headers=headers,
            json={
                "wallet_id": wallet,
                "answers": answers,
                "expected_version": 1,
            },
        ).status_code
        == 200
    )
    _send(client, pg_engine, chat_id, "¿Recuerdas mi negocio?")
    assert "Panadería de Ana" in str(seen[-1])
    assert "Cafetería de Ana" not in str(seen[-1])


def test_app_chat_retries_and_pagination(client):  # noqa: F811
    headers, wallet = account(client)
    request_id = str(uuid.uuid4())
    first = post_chat(client, headers, wallet, "aYuDa.", request_id=request_id)
    assert first.status_code == 200, first.text
    retry = post_chat(client, headers, wallet, "aYuDa.", request_id=request_id)
    assert retry.json() == first.json()
    assert (
        post_chat(client, headers, wallet, "Otra pregunta", request_id=request_id).status_code
        == 409
    )
    second = post_chat(client, headers, wallet, "rezumen").json()
    assert "¿Quisiste decir Resumen?" in second["reply"]
    third = post_chat(client, headers, wallet, "Ayuda").json()
    url = f"/api/v1/agent/chat?wallet_id={wallet}&limit=2"
    page = client.get(url, headers=headers).json()
    assert [item["id"] for item in page["items"]] == [second["id"], third["id"]]
    previous = client.get(url + f"&cursor={page['next_cursor']}", headers=headers).json()
    assert [item["id"] for item in previous["items"]] == [first.json()["id"]]
    assert previous["next_cursor"] is None


def test_memory_and_chat_are_scoped_to_owner_and_wallet(client):  # noqa: F811
    headers, wallet = account(client)
    other_headers, other_wallet = account(client)
    client.cookies.clear()
    assert (
        client.patch(
            "/api/v1/agent/profile",
            headers=headers,
            json={
                "wallet_id": wallet,
                "answers": ["PRIVATE_BUSINESS"],
                "expected_version": 0,
            },
        ).status_code
        == 200
    )
    post_chat(client, headers, wallet, "Ayuda")
    for endpoint in ("profile", "chat"):
        assert (
            client.get(
                f"/api/v1/agent/{endpoint}?wallet_id={wallet}", headers=other_headers
            ).status_code
            == 404
        )
        assert client.get(f"/api/v1/agent/{endpoint}?wallet_id={wallet}").status_code == 401
    assert post_chat(client, other_headers, wallet, "Hola").status_code == 404
    assert (
        client.patch(
            "/api/v1/agent/profile",
            headers=other_headers,
            json={
                "wallet_id": wallet,
                "answers": ["Ropa"],
                "expected_version": 1,
            },
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/agent/profile?wallet_id={other_wallet}", headers=other_headers).json()[
            "answers"
        ]
        == []
    )
    assert (
        client.get(f"/api/v1/agent/chat?wallet_id={other_wallet}", headers=other_headers).json()[
            "items"
        ]
        == []
    )
    personal = next(
        item
        for item in client.get("/api/v1/wallets", headers=headers).json()["items"]
        if item["role"] == "PRINCIPAL"
    )
    assert post_chat(client, headers, personal["id"], "Hola").status_code == 422


def test_invalid_profile_and_blank_message_are_rejected(client):  # noqa: F811
    headers, wallet = account(client)
    for answers in ([""], ["   "], ["a"] * 6, ["a" * 501]):
        response = client.patch(
            "/api/v1/agent/profile",
            headers=headers,
            json={
                "wallet_id": wallet,
                "answers": answers,
                "expected_version": 0,
            },
        )
        assert response.status_code == 422
    assert post_chat(client, headers, wallet, "   ").status_code == 422
    assert (
        client.get(f"/api/v1/agent/chat?wallet_id={wallet}&limit=1000", headers=headers).status_code
        == 422
    )


def test_app_options_change_report_preferences_without_telegram_delivery(client, pg_engine):  # noqa: F811
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.modules.messaging.models import OutboundMessage

    headers, wallet = account(client)
    assert "pausados" in post_chat(client, headers, wallet, "PAUSAR.").json()["reply"]
    assert "pausados" in post_chat(client, headers, wallet, "Resumen").json()["reply"]
    assert "activados" in post_chat(client, headers, wallet, "reanudar").json()["reply"]
    with Session(pg_engine) as db:
        count = db.scalar(select(func.count()).select_from(OutboundMessage))
    assert (
        "Tu semana en Mi Negocio" in post_chat(client, headers, wallet, "Resumen").json()["reply"]
    )
    with Session(pg_engine) as db:
        assert db.scalar(select(func.count()).select_from(OutboundMessage)) == count
