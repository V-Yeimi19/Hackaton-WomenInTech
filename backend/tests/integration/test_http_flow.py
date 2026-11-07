"""Recorrido de API completo y aislamiento de sesiones, con PostgreSQL."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(pg_engine):
    # La cuota p?blica persiste entre procesos; cada prueba usa su propia ventana l?gica.
    import hashlib

    from sqlalchemy import text

    with Session(pg_engine) as db:
        db.execute(
            text("DELETE FROM request_quotas WHERE key = :key"),
            {"key": hashlib.sha256(b"demo-sessions:testclient").hexdigest()},
        )
        db.commit()

    def database():
        with Session(pg_engine) as session:
            yield session

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def session(client, scenario="empty"):
    response = client.post("/api/v1/demo/sessions", json={"scenario": scenario})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['session_token']}"}


def test_activation_payment_withdrawal_cash_report_and_isolation(client):
    headers = session(client)
    assert (
        client.post(
            "/api/v1/business/activation",
            headers=headers,
            json={"name": "Prueba", "consent_core": False},
        ).status_code
        == 422
    )
    activation = client.post(
        "/api/v1/business/activation",
        headers=headers,
        json={"name": "Prueba", "consent_core": True},
    )
    assert activation.status_code == 201, activation.text
    token = activation.json()["qr_token"]
    sale = client.post(f"/api/v1/demo/qr/{token}/sales", json={"amount": "200.00"})
    assert sale.status_code == 202, sale.text
    headers["Idempotency-Key"] = uuid.uuid4().hex
    payment = client.post("/api/v1/payments", headers=headers, json={"amount": "50.00"})
    assert payment.status_code == 201, payment.text
    transaction_id = payment.json()["transaction_id"]
    assert (
        client.post("/api/v1/payments", headers=headers, json={"amount": "50.00"}).json()
        == payment.json()
    )
    headers["Idempotency-Key"] = uuid.uuid4().hex
    withdrawal = client.post(
        "/api/v1/household-transfers",
        headers=headers,
        json={"amount": "60.00", "direction": "BUSINESS_TO_HOME"},
    )
    assert withdrawal.status_code == 201, withdrawal.text
    headers["Idempotency-Key"] = uuid.uuid4().hex
    cash = client.post(
        "/api/v1/cash-records", headers=headers, json={"type": "SALE", "amount": "30.00"}
    )
    assert cash.status_code == 201, cash.text
    balance = client.get("/api/v1/business/balances", headers=headers).json()
    assert balance["business_digital"] == "90.00"
    assert balance["cash_declared"] == "30.00"
    report = client.post("/api/v1/reports/preview", headers=headers, json={"kind": "PRELIMINARY"})
    assert report.status_code == 200, report.text
    assert report.json()["report"]["metrics"]["operating_cash_flow"] == "180.00"
    other = session(client, "risk")
    correction = client.post(
        f"/api/v1/transactions/{transaction_id}/corrections",
        headers={**other, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "Prueba de aislamiento"},
    )
    assert correction.status_code == 404


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "1.001", "1E+999"])
def test_ca09_invalid_manual_money(client, amount):
    headers = session(client, "risk")
    response = client.post(
        "/api/v1/payments",
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"amount": amount},
    )
    assert response.status_code == 422, response.text


def test_two_scenarios_have_independent_channels(client):
    first = session(client, "risk")
    second = session(client, "risk")
    for headers in (first, second):
        response = client.post(
            "/api/v1/demo/simulate-whatsapp", headers=headers, json={"body": "RESUMEN"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["messages"]


def test_ca08_classification_changes_household_once(client):
    headers = session(client, "stable")
    headers["Idempotency-Key"] = uuid.uuid4().hex
    payment = client.post(
        "/api/v1/payments", headers=headers, json={"amount": "40", "ambiguous": True}
    )
    assert payment.status_code == 201, payment.text
    before = payment.json()["balances"]
    request_id = payment.json()["classification_request_id"]
    headers["Idempotency-Key"] = uuid.uuid4().hex
    payload = {"option": "HOUSEHOLD_WITHDRAWAL", "expected_version": 1}
    path = f"/api/v1/classifications/{request_id}/resolution"
    first = client.post(path, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert client.post(path, headers=headers, json=payload).json() == first.json()
    after = client.get("/api/v1/business/balances", headers=headers).json()
    from decimal import Decimal

    assert after["business_digital"] == before["business_digital"]
    assert Decimal(after["household_digital"]) == Decimal(before["household_digital"]) + 40


def test_ca23_http_correction_retry_returns_original_result(client):
    headers = session(client, "stable")
    headers["Idempotency-Key"] = uuid.uuid4().hex
    sale = client.post(
        "/api/v1/cash-records", headers=headers, json={"type": "SALE", "amount": "50"}
    )
    assert sale.status_code == 201, sale.text
    path = f"/api/v1/transactions/{sale.json()['transaction_id']}/corrections"
    headers["Idempotency-Key"] = uuid.uuid4().hex
    payload = {"reason": "Corrección de prueba", "replacement": {"amount": "30", "medium": "CASH"}}
    first = client.post(path, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert client.post(path, headers=headers, json=payload).json() == first.json()


def test_ca10_invalid_twilio_signature_is_forbidden(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "messaging_mode", "twilio")
    monkeypatch.setattr(settings, "twilio_auth_token", "test-secret")
    response = client.post(
        "/api/v1/webhooks/twilio/whatsapp",
        data={"MessageSid": "bad"},
        headers={"X-Twilio-Signature": "invalid"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"source": "PROVIDER_CONFIRMED"},
        {"amount": "NaN"},
        {"currency": "USD"},
        {"occurred_at": "2026-11-07T10:00:00"},
    ],
)
def test_ca09_ca24_signed_invalid_simulator_event_is_rejected(client, change):
    import json
    import time

    from app.core.security import sign_simulator_payload

    event = {
        "event_id": uuid.uuid4().hex,
        "event_type": "transaction.confirmed",
        "external_transaction_id": uuid.uuid4().hex,
        "business_reference": str(uuid.uuid4()),
        "kind": "SALE",
        "amount": "10",
        "currency": "PEN",
        "source": "SIMULATED",
        "occurred_at": "2026-11-07T10:00:00-05:00",
        **change,
    }
    raw = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    response = client.post(
        "/api/v1/webhooks/simulator/transactions",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Mica-Timestamp": timestamp,
            "X-Mica-Signature": sign_simulator_payload(timestamp, raw),
        },
    )
    assert response.status_code == 422, response.text


def test_education_and_minimized_usage_events(client):
    headers = session(client, "risk")
    assert client.get("/api/v1/education/recommendation", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/usage-events", headers=headers, json={"event": "REPORT_OPENED"}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/v1/usage-events",
            headers=headers,
            json={"event": "REPORT_OPENED", "amount": "100"},
        ).status_code
        == 422
    )
