"""Integridad financiera y recuperación con PostgreSQL real."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.identity.models import ChannelLink
from app.modules.insights.service import compute_metrics
from app.modules.ledger import domain as d
from app.modules.ledger import service as ledger
from app.modules.ledger.models import LedgerEntry, Transaction
from app.modules.messaging import service as messaging
from app.modules.messaging.models import OutboundMessage

pytestmark = pytest.mark.integration


def post(db, business, kind, amount, **kwargs):
    return ledger.post(
        db,
        business_id=business.id,
        kind=kind,
        amount=Decimal(amount),
        source=d.SIMULATED,
        occurred_at=utcnow(),
        **kwargs,
    )


def test_ca02_ca03_external_deduplication(db, business):
    external = uuid.uuid4().hex
    ids = {
        post(db, business, d.SALE, "120", provider="simulator", external_transaction_id=external).id
        for _ in range(10)
    }
    assert len(ids) == 1
    assert ledger.balances(db, business.id)["business_digital"] == "120.00"
    assert (
        db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.business_id == business.id)
        )
        == 2
    )


def test_ca04_ca06_ca07_ca12_numerical_example(db, business):
    post(db, business, d.OPENING_BALANCE, "300", target_account_kind=d.HOUSEHOLD_DIGITAL)
    post(db, business, d.SALE, "1200")
    post(db, business, d.SALE, "300", medium=d.CASH)
    post(db, business, d.BUSINESS_PAYMENT, "800")
    post(db, business, d.OWNER_CONTRIBUTION, "300")
    post(db, business, d.HOUSEHOLD_WITHDRAWAL, "600")
    metrics = compute_metrics(db, business.id, utcnow() - timedelta(days=1), utcnow())
    assert metrics.operating_flow == Decimal("700")
    assert ledger.balances(db, business.id) == {
        "business_digital": "100.00",
        "household_digital": "600.00",
        "cash_declared": "300.00",
    }
    from app.modules.commitments.schemas import CommitmentCreate
    from app.modules.commitments.service import create, upcoming_shortfall

    create(
        db,
        business.id,
        CommitmentCreate(label="Proveedor", amount="1500", due_at=utcnow() + timedelta(days=1)),
    )
    assert upcoming_shortfall(db, business.id)["DIGITAL"] == Decimal("1400")


def test_ca05_concurrent_withdrawals(db, business, pg_engine):
    post(db, business, d.SALE, "100")
    business_id = business.id

    def withdraw():
        with Session(pg_engine) as session:
            try:
                ledger.post(
                    session,
                    business_id=business_id,
                    kind=d.HOUSEHOLD_WITHDRAWAL,
                    amount=Decimal("80"),
                    source=d.USER_DECLARED,
                    occurred_at=utcnow(),
                )
                return "POSTED"
            except AppError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: withdraw(), range(2)))
    assert sorted(results) == ["INSUFFICIENT_BALANCE", "POSTED"]
    assert ledger.balances(db, business_id)["business_digital"] == "20.00"


def test_ca23_compensation_once(db, business):
    original = post(db, business, d.SALE, "100")
    first = ledger.post_reversal(db, original, reason="Prueba")
    second = ledger.post_reversal(db, original, reason="Prueba")
    assert first.id == second.id
    assert ledger.balances(db, business.id)["business_digital"] == "0.00"
    assert db.get(Transaction, original.id).amount == Decimal("100")


def test_ca28_idempotency_conflict(db, business):
    def execute():
        tx = ledger.post(
            db,
            business_id=business.id,
            kind=d.SALE,
            amount=Decimal("10"),
            source=d.SIMULATED,
            occurred_at=utcnow(),
            commit=False,
        )
        return 201, {"id": str(tx.id)}

    args = dict(business_id=business.id, route="test", key="same", fn=execute)
    first = ledger.run_idempotent(db, payload={"amount": "10"}, **args)
    assert ledger.run_idempotent(db, payload={"amount": "10"}, **args) == first
    with pytest.raises(AppError, match="otro cuerpo"):
        ledger.run_idempotent(db, payload={"amount": "20"}, **args)
    assert ledger.balances(db, business.id)["business_digital"] == "10.00"


def test_ca22_timeout_is_unknown_without_resending(db, message, monkeypatch):
    calls = []

    def timeout(*args):
        calls.append(args)
        raise TimeoutError("Resultado incierto")

    monkeypatch.setattr(messaging.twilio_gateway, "send_text", timeout)
    messaging.deliver_message(db, message)
    assert message.status == "UNKNOWN"
    messaging.deliver_message(db, message)
    assert len(calls) == 1


def test_ca20_window_without_template_is_blocked(db, message, monkeypatch):
    link = db.get(ChannelLink, message.channel_link_id)
    link.last_inbound_at = utcnow() - timedelta(hours=25)
    db.commit()
    monkeypatch.setattr(messaging.settings, "messaging_mode", "twilio")
    monkeypatch.setattr(
        messaging.twilio_gateway, "send_text", lambda *a: pytest.fail("Envío indebido")
    )
    messaging.deliver_message(db, message)
    assert message.status == "BLOCKED"


def test_ca27_delivery_never_regresses(db, message):
    message.provider_sid = uuid.uuid4().hex
    message.status = "ACCEPTED"
    db.commit()
    for status in ("DELIVERED", "ACCEPTED", "FAILED"):
        messaging.record_delivery_event(
            db, provider_sid=message.provider_sid, status=status, payload_hash=uuid.uuid4().hex
        )
    assert db.get(OutboundMessage, message.id).status == "DELIVERED"
