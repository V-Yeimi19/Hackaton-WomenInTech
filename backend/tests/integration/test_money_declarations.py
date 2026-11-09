"""Confirmación real contra PostgreSQL: el LLM propone, el usuario autoriza."""
# ruff: noqa: F811

import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import channel_lookup_hash
from app.db.base import utcnow
from app.integrations import audio_gateway, llm_gateway, telegram_gateway
from app.modules.agent.models import MoneyDeclaration
from app.modules.identity.models import ChannelLink
from app.modules.ledger.models import LedgerEntry, Transaction
from app.modules.messaging.models import OutboundMessage
from tests.integration.test_agent_channels import account, post_chat
from tests.integration.test_http_flow import client  # noqa: F401
from tests.integration.test_telegram_audio_flow import audio_update, process
from tests.integration.test_telegram_flow import _send

pytestmark = pytest.mark.integration
settings = get_settings()
TEXT = "Hoy vendí 500 soles en mi negocio, 300 fueron en Yape y 200 en efectivo, y gasté 80 soles de efectivo en mercadería. También gasté de mi billetera personal de Yape 30 soles en transporte."


def report(text=TEXT, expense="80.00"):
    return {
        "intent": "record",
        "entries": [
            {
                "wallet": "negocio",
                "medium": "DIGITAL",
                "direction": "IN",
                "amount": "300.00",
                "description": "Ventas por Yape",
                "evidence": text,
            },
            {
                "wallet": "negocio",
                "medium": "CASH",
                "direction": "IN",
                "amount": "200.00",
                "description": "Ventas en efectivo",
                "evidence": text,
            },
            {
                "wallet": "negocio",
                "medium": "CASH",
                "direction": "OUT",
                "amount": expense,
                "description": "Mercadería",
                "evidence": text,
            },
            {
                "wallet": "principal",
                "medium": "DIGITAL",
                "direction": "OUT",
                "amount": "30.00",
                "description": "Transporte personal",
                "evidence": text,
            },
        ],
        "reported_sales_totals": [{"wallet": "negocio", "amount": "500.00"}],
        "questions": [],
    }


def single(text, amount="50.00", wallet="negocio", direction="IN", medium="CASH"):
    return {
        "intent": "record",
        "entries": [
            {
                "wallet": wallet,
                "medium": medium,
                "direction": direction,
                "amount": amount,
                "description": "Movimiento declarado",
                "evidence": text,
            }
        ],
        "reported_sales_totals": [],
        "questions": [],
    }


@pytest.fixture
def money(client, monkeypatch):
    headers, wallet = account(client)
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "groq_model", "test-model")
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "whatsapp_enabled", False)
    value = report()

    def chat(messages, **kwargs):
        assert kwargs.get("json_mode") is True
        return json.dumps(value, ensure_ascii=False)

    monkeypatch.setattr(llm_gateway, "chat", chat)
    return headers, wallet, value


def wallets(client, headers):
    return client.get("/api/v1/wallets", headers=headers).json()


def send(client, money, text, **extra):
    headers, wallet, _ = money
    response = post_chat(client, headers, wallet, text, **extra)
    assert response.status_code == 200, response.text
    return response.json()


def action(client, money, message, name="confirm", **extra):
    state = message["declaration"]
    return send(
        client,
        money,
        {"confirm": "Confirmar", "edit": "Editar", "cancel": "Cancelar"}[name],
        declaration_action={"id": state["id"], "version": state["version"], "action": name},
        **extra,
    )


def test_example_only_posts_cash_after_review_and_confirmation(client, pg_engine, money):
    headers, wallet_id, _ = money
    before = wallets(client, headers)
    first = send(client, money, TEXT)
    assert "Antes de estos movimientos" in first["reply"]
    assert "confirm" in first["declaration"]["actions"]
    incomplete = action(client, money, first)
    assert "Antes de estos movimientos" in incomplete["reply"]
    assert incomplete["declaration"]["status"] == "PENDING"
    assert (
        wallets(client, headers) == before or wallets(client, headers)["items"] == before["items"]
    )
    review = send(client, money, "0")
    assert "S/ 300.00" in review["reply"] and "S/ 200.00" in review["reply"]
    assert "S/ 80.00" in review["reply"] and "S/ 30.00" in review["reply"]
    assert "120.00" in review["reply"]
    assert "confirm" in review["declaration"]["actions"]
    assert wallets(client, headers)["items"] == before["items"]
    request_id = str(uuid.uuid4())
    confirmed = action(client, money, review, request_id=request_id)
    assert confirmed["declaration"]["status"] == "CONFIRMED"
    after = wallets(client, headers)
    for old, new in zip(before["items"], after["items"], strict=True):
        assert old["balance"] == new["balance"]  # Yape no se abona ni se descuenta otra vez
        assert new["cash_balance"] == ("120.00" if new["id"] == wallet_id else None)
    assert after["cash_total"] == "120.00"
    assert action(client, money, review, request_id=request_id) == confirmed
    assert "No volví" in action(client, money, review)["reply"]
    assert wallets(client, headers)["cash_total"] == "120.00"
    rows = client.get(f"/api/v1/movements?wallet_id={wallet_id}", headers=headers).json()["items"]
    cash = [row for row in rows if row["medium"] == "CASH"]
    assert sorted(row["amount"] for row in cash) == ["-80.00", "200.00"]
    with Session(pg_engine) as db:
        business_id = client.get("/api/v1/me", headers=headers).json()["business_id"]
        cash_rows = db.scalars(
            select(Transaction).where(
                Transaction.business_id == uuid.UUID(business_id),
                Transaction.medium == "CASH",
                Transaction.kind != "OPENING_BALANCE",
            )
        ).all()
        for transaction in cash_rows:
            assert (
                db.scalar(
                    select(func.sum(LedgerEntry.delta)).where(
                        LedgerEntry.transaction_id == transaction.id
                    )
                )
                == 0
            )


def test_cancel_does_not_initialize_cash_or_post_anything(client, money):
    headers, _, _ = money
    before = wallets(client, headers)["items"]
    review = send(client, money, TEXT)
    cancelled = action(client, money, review, "cancel")
    assert cancelled["declaration"]["status"] == "CANCELLED"
    assert wallets(client, headers)["items"] == before
    assert action(client, money, review)["declaration"]["status"] == "CANCELLED"


def test_failure_during_posting_rolls_back_the_entire_batch(client, money, monkeypatch):
    from app.core.errors import AppError
    from app.modules.wallets import service as wallet_service

    send(client, money, TEXT)
    review = send(client, money, "0")
    before = wallets(client, money[0])["items"]
    original = wallet_service.record_cash
    calls = []

    def fail_on_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise AppError("TEST_POST_FAILURE", "Fallo transitorio de prueba.", 409)
        return original(*args, **kwargs)

    monkeypatch.setattr(wallet_service, "record_cash", fail_on_second)
    control = {
        "id": review["declaration"]["id"],
        "version": review["declaration"]["version"],
        "action": "confirm",
    }
    response = post_chat(client, money[0], money[1], "Confirmar", declaration_action=control)
    assert response.status_code == 409
    assert wallets(client, money[0])["items"] == before
    monkeypatch.setattr(wallet_service, "record_cash", original)
    assert action(client, money, review)["declaration"]["status"] == "CONFIRMED"
    assert wallets(client, money[0])["cash_total"] == "120.00"


def test_two_simultaneous_confirmations_do_not_double_cash(client, money):
    send(client, money, TEXT)
    review = send(client, money, "0")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: action(client, money, review), range(2)))
    assert all(result["declaration"]["status"] == "CONFIRMED" for result in results)
    assert wallets(client, money[0])["cash_total"] == "120.00"


def test_edit_and_old_confirm_button_cannot_post_stale_amounts(client, money):
    send(client, money, TEXT)
    old_review = send(client, money, "0")
    action(client, money, old_review, "edit")
    changed_text = TEXT.replace("80 soles", "90 soles")
    money[2].clear()
    money[2].update(report(changed_text, "90.00"))
    send(client, money, changed_text)
    current = send(client, money, "0")
    stale = action(client, money, old_review)
    assert "versión actualizada" in stale["reply"]
    assert wallets(client, money[0])["cash_total"] == "0.00"
    assert action(client, money, current)["declaration"]["status"] == "CONFIRMED"
    assert wallets(client, money[0])["cash_total"] == "110.00"


def test_initial_cash_is_remembered_and_not_counted_as_sales(client, money):
    text = "Hoy vendí 50 soles en efectivo en mi negocio"
    money[2].clear()
    money[2].update(single(text))
    before = wallets(client, money[0])
    send(client, money, text)
    review = send(client, money, "100")
    assert "150.00" in review["reply"]
    action(client, money, review)
    snapshot = wallets(client, money[0])
    assert snapshot["cash_total"] == "150.00"
    old_legacy = Decimal(before["unallocated_cash"])
    assert Decimal(snapshot["unallocated_cash"]) == max(Decimal("0"), old_legacy - 100)
    # El efectivo legado se reasigna, no se duplica.
    assert (
        Decimal(snapshot["cash_total"]) + Decimal(snapshot["unallocated_cash"])
        == old_legacy + max(Decimal("0"), 100 - old_legacy) + 50
    )
    next_text = "Hoy vendí 60 soles en efectivo en mi negocio"
    money[2].clear()
    money[2].update(single(next_text, "60.00"))
    next_review = send(client, money, next_text)
    assert "Antes de estos movimientos" not in next_review["reply"]
    assert "confirm" in next_review["declaration"]["actions"]
    action(client, money, next_review)
    assert wallets(client, money[0])["cash_total"] == "210.00"


def test_insufficient_cash_rolls_back_every_wallet(client, money):
    text = "Hoy vendí 200 soles en efectivo en mi negocio y gasté 30 soles de efectivo de mi billetera principal"
    data = single(text, "200.00")
    data["entries"].append(single(text, "30.00", wallet="principal", direction="OUT")["entries"][0])
    money[2].clear()
    money[2].update(data)
    send(client, money, text)
    assert "Principal" in send(client, money, "0")["reply"]
    review = send(client, money, "0")
    failed = action(client, money, review)
    assert "No registré ningún movimiento" in failed["reply"]
    assert all(item["cash_balance"] is None for item in wallets(client, money[0])["items"])
    assert failed["declaration"]["status"] == "PENDING"


def test_business_and_personal_cash_remain_separate_in_balances_and_reports(
    client, pg_engine, money
):
    from app.modules.insights.service import compute_metrics
    from app.shared.clock import week_start

    text = "Hoy vendí 200 soles en efectivo en mi negocio y gasté 30 soles de efectivo de mi billetera principal"
    data = single(text, "200.00")
    data["entries"].append(single(text, "30.00", wallet="principal", direction="OUT")["entries"][0])
    money[2].clear()
    money[2].update(data)
    send(client, money, text)
    send(client, money, "0")
    review = send(client, money, "100")
    action(client, money, review)
    snapshot = wallets(client, money[0])
    business = next(w for w in snapshot["items"] if w["id"] == money[1])
    personal = next(w for w in snapshot["items"] if w["role"] == "PRINCIPAL")
    assert business["cash_balance"] == "200.00"
    assert personal["cash_balance"] == "70.00"
    assert snapshot["cash_total"] == "270.00"
    business_id = uuid.UUID(client.get("/api/v1/me", headers=money[0]).json()["business_id"])
    with Session(pg_engine) as db:
        start = week_start(utcnow())
        metrics = compute_metrics(
            db,
            business_id,
            start,
            start + timedelta(days=7),
            cutoff=utcnow() + timedelta(seconds=1),
        )
        assert metrics.declared_cash_balance == Decimal(snapshot["unallocated_cash"]) + Decimal(
            "200.00"
        )


def test_foreign_currency_or_unspecified_medium_is_not_guessed(client, money):
    first = send(client, money, "Hoy vendí 500 dólares en efectivo en mi negocio")
    assert "Solo puedo registrar soles" in first["reply"]
    assert first["declaration"] is None
    money[2].clear()
    money[2].update(single("Hoy vendí 50 soles en mi negocio"))
    second = send(client, money, "Hoy vendí 50 soles en mi negocio")
    assert second["declaration"]["status"] == "EDITING"
    assert "confirm" in second["declaration"]["actions"]
    assert action(client, money, second)["declaration"]["status"] == "EDITING"


@pytest.mark.parametrize("change", ["total", "medium", "wallet", "amount"])
def test_ambiguous_or_inconsistent_reports_require_editing(client, money, change):
    if change == "total":
        money[2]["reported_sales_totals"][0]["amount"] = (
            "420.00"  # El saldo neto no es el total bruto de ventas.
        )
    elif change == "medium":
        money[2]["entries"][1]["medium"] = "UNKNOWN"
    elif change == "wallet":
        money[2]["entries"][1]["wallet"] = "Billetera inexistente"
    else:
        money[2]["entries"][1]["amount"] = "999.00"
    message = send(client, money, TEXT)
    assert message["declaration"]["status"] == "EDITING"
    assert "confirm" in message["declaration"]["actions"]
    assert action(client, money, message)["declaration"]["status"] == "EDITING"
    assert "CONFIRMED" not in action(client, money, message)["declaration"]["status"]
    assert wallets(client, money[0])["cash_total"] == "0.00"


def test_declaration_actions_are_scoped_to_account_and_expire(client, pg_engine, money):
    first = send(client, money, TEXT)
    other_headers, other_wallet = account(client)
    response = post_chat(
        client,
        other_headers,
        other_wallet,
        "Confirmar",
        declaration_action={
            "id": first["declaration"]["id"],
            "version": first["declaration"]["version"],
            "action": "confirm",
        },
    )
    assert response.status_code == 404
    with Session(pg_engine) as db:
        draft = db.get(MoneyDeclaration, uuid.UUID(first["declaration"]["id"]))
        draft.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    expired = action(client, money, first)
    assert expired["declaration"]["status"] == "EXPIRED"
    assert wallets(client, money[0])["cash_total"] == "0.00"


def linked(client, pg_engine, money):
    code = client.post("/api/v1/channel-link-challenges", headers=money[0]).json()["code"]
    chat_id = random.randint(10**9, 10**10)
    _send(client, pg_engine, chat_id, f"/start {code}")
    return chat_id


def last_reply(pg_engine, chat_id):
    with Session(pg_engine) as db:
        link = db.scalar(
            select(ChannelLink).where(
                ChannelLink.provider == "telegram",
                ChannelLink.phone_lookup_hash == channel_lookup_hash("telegram", str(chat_id)),
            )
        )
        message = db.scalar(
            select(OutboundMessage)
            .where(OutboundMessage.channel_link_id == link.id)
            .order_by(OutboundMessage.created_at.desc())
        )
        return message.reply_markup


def callback(chat_id, data):
    return {
        "update_id": random.randint(10**8, 10**9),
        "callback_query": {
            "id": uuid.uuid4().hex,
            "from": {"id": chat_id},
            "message": {"message_id": 1, "chat": {"id": chat_id, "type": "private"}},
            "data": data,
        },
    }


def test_audio_confirmation_buttons_update_app_and_duplicate_callback_is_harmless(
    client, pg_engine, money, monkeypatch
):
    chat_id = linked(client, pg_engine, money)
    monkeypatch.setattr(audio_gateway, "is_enabled", lambda: True)
    monkeypatch.setattr(telegram_gateway, "download_audio", lambda file_id: (b"audio", "audio.ogg"))
    monkeypatch.setattr(audio_gateway, "transcribe", lambda *a: TEXT)
    first, transcript = process(client, pg_engine, audio_update(chat_id))
    assert transcript == TEXT and "Antes de estos movimientos" in first
    initial_buttons = last_reply(pg_engine, chat_id)["inline_keyboard"][0]
    assert [b["text"] for b in initial_buttons] == ["Confirmar", "Editar", "Cancelar"]
    incomplete, _ = process(
        client, pg_engine, callback(chat_id, initial_buttons[0]["callback_data"])
    )
    assert "Antes de estos movimientos" in incomplete
    assert wallets(client, money[0])["cash_total"] == "0.00"
    _send(client, pg_engine, chat_id, "0")
    markup = last_reply(pg_engine, chat_id)
    button = next(b for b in markup["inline_keyboard"][0] if b["text"] == "Confirmar")
    update = callback(chat_id, button["callback_data"])
    confirmed, _ = process(client, pg_engine, update)
    assert "Información confirmada" in confirmed
    process(client, pg_engine, update)
    assert wallets(client, money[0])["cash_total"] == "120.00"
    memory = client.get(f"/api/v1/agent/declarations?wallet_id={money[1]}", headers=money[0]).json()
    assert len(memory["latest_confirmed"]["entries"]) == 4
    # Solo memoria estructurada compartida, no mensajes del chat de Telegram.
    assert (
        client.get(f"/api/v1/agent/chat?wallet_id={money[1]}", headers=money[0]).json()["items"]
        == []
    )


def test_cash_changed_in_another_channel_requires_new_review(client, pg_engine, money):
    send(client, money, TEXT)
    app_review = send(client, money, "0")
    chat_id = linked(client, pg_engine, money)
    _send(client, pg_engine, chat_id, TEXT)
    _send(client, pg_engine, chat_id, "0")
    old_button = next(
        b for b in last_reply(pg_engine, chat_id)["inline_keyboard"][0] if b["text"] == "Confirmar"
    )
    action(client, money, app_review)
    message, _ = process(client, pg_engine, callback(chat_id, old_button["callback_data"]))
    assert "El efectivo cambió" in message
    assert wallets(client, money[0])["cash_total"] == "120.00"


def test_telegram_cancel_button_never_confirms(client, pg_engine, money):
    chat_id = linked(client, pg_engine, money)
    _send(client, pg_engine, chat_id, TEXT)
    _send(client, pg_engine, chat_id, "0")
    button = next(
        b for b in last_reply(pg_engine, chat_id)["inline_keyboard"][0] if b["text"] == "Cancelar"
    )
    result, _ = process(client, pg_engine, callback(chat_id, button["callback_data"]))
    assert "Cancelado" in result
    assert wallets(client, money[0])["cash_total"] == "0.00"


@pytest.mark.parametrize(
    ("spoken", "amount", "remaining"),
    [("veinte", "20.00", "80.00"), ("veinte soles con cincuenta céntimos", "20.50", "79.50")],
)
def test_spelled_money_and_numeric_product_description_keep_correct_amount(
    client, money, spoken, amount, remaining
):
    text = f"Hoy gasté {spoken} soles en efectivo de mi negocio por dos sacos de azúcar"
    money[2].clear()
    money[2].update(single(text, amount=amount, direction="OUT"))
    money[2]["entries"][0]["description"] = "dos sacos de azúcar"
    first = send(client, money, text)
    assert first["declaration"]["status"] == "PENDING"
    review = send(client, money, "100")
    assert f"S/ {amount}" in review["reply"]
    assert "dos sacos de azúcar" in review["reply"]
    confirmed = action(client, money, review)
    assert confirmed["declaration"]["status"] == "CONFIRMED"
    result = wallets(client, money[0])
    assert next(w for w in result["items"] if w["id"] == money[1])["cash_balance"] == remaining


def test_product_quantity_cannot_be_used_as_money_amount(client, money):
    text = "Hoy gasté veinte soles en efectivo de mi negocio por dos sacos de azúcar"
    money[2].clear()
    money[2].update(single(text, amount="2.00", direction="OUT"))
    reply = send(client, money, text)
    assert reply["declaration"]["status"] == "EDITING"
    assert "aclares los importes" in reply["reply"]
