"""Telegram: periodo pendiente, selección de negocio, PDF privado y cifras sin duplicar."""
# ruff: noqa: F811

import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.integrations import telegram_gateway
from app.modules.agent import dashboards
from app.modules.agent.models import MoneyDeclaration
from app.modules.business.models import Business
from app.modules.identity.models import ChannelLink
from app.modules.ledger import service as ledger
from app.modules.messaging import service as messaging
from app.modules.messaging.models import DashboardRequest, OutboundMessage
from app.modules.wallets import service as wallets
from app.modules.wallets.models import Wallet
from app.shared.clock import business_tz
from tests.integration.test_agent_channels import account
from tests.integration.test_http_flow import client  # noqa: F401
from tests.integration.test_telegram_flow import _send, _update

pytestmark = pytest.mark.integration


def linked(client, pg_engine):
    headers, wallet_id = account(client)
    code = client.post("/api/v1/channel-link-challenges", headers=headers).json()["code"]
    chat = random.randint(10**9, 10**10)
    _send(client, pg_engine, chat, f"/start {code}")
    with Session(pg_engine) as db:
        wallet = db.get(Wallet, uuid.UUID(wallet_id))
        business_id = wallet.business_id
        link = db.scalar(
            select(ChannelLink).where(
                ChannelLink.business_id == business_id, ChannelLink.provider == "telegram"
            )
        )
        return headers, chat, wallet.id, business_id, link.id


def last(db, link_id):
    return db.scalar(
        select(OutboundMessage)
        .where(OutboundMessage.channel_link_id == link_id)
        .order_by(OutboundMessage.created_at.desc())
    )


@pytest.mark.parametrize("period_reply", ["ESTA SEMANA.", "Últimos dos días."])
def test_pdf_asks_period_and_sends_once_via_private_document(
    client, pg_engine, monkeypatch, period_reply
):
    _, chat, _, _, link_id = linked(client, pg_engine)
    delivered = []
    original = telegram_gateway.send_document

    def capture(address, content, filename, caption):
        delivered.append((address, content, filename))
        return original(address, content, filename, caption)

    monkeypatch.setattr(telegram_gateway, "send_document", capture)
    response = _send(client, pg_engine, chat, "Quiero un PDF")
    assert "¿De qué periodo" in response[-1]
    with Session(pg_engine) as db:
        assert last(db, link_id).document is None
    update = _update(chat, period_reply)
    for _ in range(2):
        assert client.post("/api/v1/webhooks/telegram", json=update).status_code == 200
        with Session(pg_engine) as db:
            messaging.process_pending_inbound(db)
            messaging.deliver_pending(db)
    assert len(delivered) == 1
    assert delivered[0][0] == str(chat) and delivered[0][1].startswith(b"%PDF-")
    with Session(pg_engine) as db:
        assert last(db, link_id).status == "DELIVERED"
        assert db.get(DashboardRequest, link_id) is None


@pytest.mark.parametrize(
    "scope", ["mi negocio", "mi cuenta personal", "mi negocio y cuenta personal"]
)
@pytest.mark.parametrize("number", ["3", "tres"])
def test_complete_pdf_request_sends_without_pending_selection(client, pg_engine, scope, number):
    _, chat, _, _, link_id = linked(client, pg_engine)
    messages = _send(
        client,
        pg_engine,
        chat,
        f"Generame un PDF con la información de los últimos {number} días de {scope}",
    )
    assert "Tu resumen visual" in messages[-1]
    with Session(pg_engine) as db:
        message = last(db, link_id)
        assert message.document is not None and message.status == "DELIVERED"
        assert len(message.document["days"]) == 3
        assert message.document["includes_personal"] == ("personal" in scope)
        assert len(message.document["wallet_names"]) == (2 if "y cuenta personal" in scope else 1)
        if "y cuenta personal" in scope:
            reports = message.document["wallet_reports"]
            assert len(reports) == 2
            for field in ("income", "expense", "net", "declared_digital"):
                assert Decimal(message.document[field]) == sum(Decimal(r[field]) for r in reports)
        assert db.get(DashboardRequest, link_id) is None


def test_pdf_processing_failure_notifies_after_retries(client, pg_engine, monkeypatch):
    _, chat, _, _, link_id = linked(client, pg_engine)

    def broken(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(dashboards, "snapshot", broken)
    update = _update(chat, "PDF de hoy")
    assert client.post("/api/v1/webhooks/telegram", json=update).status_code == 200
    from app.modules.messaging.models import InboundEvent

    with Session(pg_engine) as db:
        event = db.scalar(
            select(InboundEvent).where(
                InboundEvent.provider == "telegram",
                InboundEvent.event_id == str(update["update_id"]),
            )
        )
        event.attempts = messaging.MAX_ATTEMPTS - 1
        db.commit()
        messaging.process_inbound(db, event)
        messaging.deliver_pending(db)
        assert event.status == "DEAD"
        assert "No pude preparar tu PDF" in last(db, link_id).body
        assert last(db, link_id).status == "DELIVERED"


def test_pdf_multiple_businesses_and_invalid_dates_require_clarification(client, pg_engine):
    headers, chat, _, _, link_id = linked(client, pg_engine)
    response = client.post(
        "/api/v1/wallets",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"name": "Café", "purpose": "BUSINESS"},
    )
    assert response.status_code == 201, response.text
    messages = _send(client, pg_engine, chat, "PDF de 31/02/2026")
    assert "Revisa las fechas" in messages[-1]
    messages = _send(client, pg_engine, chat, "hoy")
    assert "¿De qué negocio" in messages[-1]
    messages = _send(client, pg_engine, chat, "Café")
    assert "Tu resumen visual de Café" in messages[-1]
    with Session(pg_engine) as db:
        assert last(db, link_id).document["wallet_names"] == ["Café"]


@pytest.mark.parametrize("followup", [False, True])
def test_all_wallets_include_personal_savings_and_business_across_period_followup(
    client, pg_engine, followup
):
    headers, chat, _, _, link_id = linked(client, pg_engine)
    owned = client.get("/api/v1/wallets", headers=headers).json()["items"]
    assert {w["purpose"] for w in owned} >= {"PERSONAL", "BUSINESS", "SAVINGS"}
    _send(
        client,
        pg_engine,
        chat,
        "PDF de todas mis billeteras" + ("" if followup else " de los últimos dos días"),
    )
    if followup:
        _send(client, pg_engine, chat, "Últimos dos días.")
    with Session(pg_engine) as db:
        doc = last(db, link_id).document
        assert doc is not None
        assert set(doc["wallet_names"]) == {w["name"] for w in owned}
        assert {r["wallet_id"] for r in doc["wallet_reports"]} == {w["id"] for w in owned}
        assert len(doc["days"]) == 2
        assert last(db, link_id).status == "DELIVERED"


def test_pdf_pending_is_scoped_expires_and_can_cancel(client, pg_engine):
    _, chat, _, _, link_id = linked(client, pg_engine)
    _, other_chat, _, _, other_link = linked(client, pg_engine)
    _send(client, pg_engine, chat, "PDF")
    _send(client, pg_engine, other_chat, "hoy")
    with Session(pg_engine) as db:
        assert last(db, other_link).document is None
        request = db.get(DashboardRequest, link_id)
        request.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    _send(client, pg_engine, chat, "hoy")
    with Session(pg_engine) as db:
        assert last(db, link_id).document is None
    _send(client, pg_engine, chat, "PDF")
    messages = _send(client, pg_engine, chat, "Cancelar")
    assert "Cancelé el PDF" in messages[-1]


def declaration(db, business_id, wallet_id, when, amount, *, medium="DIGITAL", status="CONFIRMED"):
    db.add(
        MoneyDeclaration(
            business_id=business_id,
            channel="telegram",
            channel_key="test",
            source_id=str(uuid.uuid4()),
            source_text="test",
            data={
                "entries": [
                    {
                        "wallet_id": str(wallet_id),
                        "wallet_name": "Negocio",
                        "medium": medium,
                        "direction": "IN",
                        "amount": amount,
                        "day": "2020-01-01",
                        "description": "ventas",
                    }
                ]
            },
            openings={},
            balance_snapshot={},
            status=status,
            version=1,
            created_at=when,
            expires_at=when + timedelta(minutes=30),
            confirmed_at=when if status == "CONFIRMED" else None,
        )
    )


def test_snapshot_counts_cash_once_and_digital_fallback_without_personal(client, pg_engine):
    _, _, wallet_id, business_id, _ = linked(client, pg_engine)
    when = datetime(2020, 1, 1, 12, tzinfo=business_tz())
    with Session(pg_engine) as db:
        business = db.get(Business, business_id)
        wallet = db.get(Wallet, wallet_id)
        principal = db.scalar(
            select(Wallet).where(Wallet.business_id == business_id, Wallet.role == "PRINCIPAL")
        )
        wallets.initialize_cash(db, wallet, "DEMO", Decimal("0"), when)
        for direction, amount in (("IN", "200"), ("OUT", "80")):
            wallets.record_cash(
                db,
                wallet,
                "DEMO",
                amount=Decimal(amount),
                direction=direction,
                occurred_at=when,
                description="test",
            )
        declaration(db, business_id, wallet.id, when, "200.00", medium="CASH")
        declaration(db, business_id, wallet.id, when, "300.00")
        declaration(db, business_id, wallet.id, when + timedelta(minutes=1), "300.00")
        declaration(db, business_id, principal.id, when, "999.00")
        declaration(db, business_id, wallet.id, when, "999.00", status="CANCELLED")
        db.commit()
        doc = dashboards.snapshot(db, business, [wallet], date(2020, 1, 1), date(2020, 1, 1))
        assert (doc["income"], doc["expense"], doc["net"]) == ("500.00", "80.00", "420.00")
        assert doc["declared_digital"] == "300.00"
        assert doc["media"]["CASH"] == {"income": "200.00", "expense": "80.00"}


def test_multiwallet_report_totals_match_each_wallet_without_internal_transfers(client, pg_engine):
    _, _, wallet_id, business_id, _ = linked(client, pg_engine)
    when = datetime(2020, 1, 1, 12, tzinfo=business_tz())
    with Session(pg_engine) as db:
        business = db.get(Business, business_id)
        wallet = db.get(Wallet, wallet_id)
        principal = db.scalar(
            select(Wallet).where(Wallet.business_id == business_id, Wallet.role == "PRINCIPAL")
        )
        for w, incoming, outgoing in ((wallet, "200", "80"), (principal, "40", "25")):
            wallets.initialize_cash(db, w, "DEMO", Decimal("0"), when)
            for direction, amount in (("IN", incoming), ("OUT", outgoing)):
                wallets.record_cash(
                    db,
                    w,
                    "DEMO",
                    amount=Decimal(amount),
                    direction=direction,
                    occurred_at=when,
                    description="prueba",
                )
        declaration(db, business_id, wallet.id, when, "300.00")
        declaration(db, business_id, principal.id, when, "20.00")
        wallets.transfer(
            db,
            business_id,
            "DEMO",
            from_wallet_id=wallet.id,
            to_wallet_id=principal.id,
            amount="1",
            occurred_at=when,
        )
        db.commit()
        doc = dashboards.snapshot(
            db, business, [wallet, principal], date(2020, 1, 1), date(2020, 1, 1)
        )
        assert (doc["income"], doc["expense"], doc["net"]) == ("560.00", "105.00", "455.00")
        assert [(r["income"], r["expense"]) for r in doc["wallet_reports"]] == [
            ("500.00", "80.00"),
            ("60.00", "25.00"),
        ]
        assert doc["wallet_reports"][0]["wallet_id"] == str(wallet.id)
        assert doc["wallet_reports"][1]["wallet_id"] == str(principal.id)
        for medium in ("CASH", "DIGITAL"):
            for field in ("income", "expense"):
                assert Decimal(doc["media"][medium][field]) == sum(
                    Decimal(r["media"][medium][field]) for r in doc["wallet_reports"]
                )
        for index, day in enumerate(doc["days"]):
            for field in ("income", "expense"):
                assert Decimal(day[field]) == sum(
                    Decimal(r["days"][index][field]) for r in doc["wallet_reports"]
                )


def test_ledger_digital_replaces_declared_and_reversals_net_out(client, pg_engine):
    _, _, wallet_id, business_id, _ = linked(client, pg_engine)
    when = datetime(2020, 1, 1, 12, tzinfo=business_tz())
    with Session(pg_engine) as db:
        business = db.get(Business, business_id)
        wallet = db.get(Wallet, wallet_id)
        account = ledger.get_account(db, business_id, "BUSINESS_DIGITAL")
        external = ledger.get_account(db, business_id, "EXTERNAL_CLEARING")
        sale = wallets.post_legs(
            db,
            business_id=business_id,
            environment="DEMO",
            kind="SALE",
            amount=Decimal("300"),
            legs=[wallets.Leg(account, Decimal("300")), wallets.Leg(external, Decimal("-300"))],
            source="SIMULATED",
            occurred_at=when,
            description="Digital real",
        )
        declaration(db, business_id, wallet_id, when, "300.00")
        db.commit()
        doc = dashboards.snapshot(db, business, [wallet], date(2020, 1, 1), date(2020, 1, 1))
        assert doc["income"] == "300.00" and doc["declared_digital"] == "0.00"
        today = utcnow().astimezone(business_tz()).date()
        previous = dashboards.snapshot(db, business, [wallet], date(2020, 1, 1), today)
        ledger.post_reversal(db, sale, reason="Anular prueba")
        # La reversión ocurre hoy; dentro del periodo completo anula la venta.
        doc = dashboards.snapshot(db, business, [wallet], date(2020, 1, 1), today)
        assert Decimal(previous["income"]) - Decimal(doc["income"]) == Decimal("300.00")
        bucket = next(d for d in doc["days"] if d["day"] == "2020-01-01")
        assert bucket["income"] == "300.00"
