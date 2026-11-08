"""Login por teléfono, billeteras, yapeos, transferencias y movimientos (PostgreSQL)."""

import hashlib
import random
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(pg_engine):
    # Las cuotas públicas persisten entre procesos: cada prueba parte con la ventana limpia.
    with Session(pg_engine) as db:
        for scope in ("phone-login", "demo-sessions"):
            db.execute(
                text("DELETE FROM request_quotas WHERE key = :key"),
                {"key": hashlib.sha256(f"{scope}:testclient".encode()).hexdigest()},
            )
        db.commit()

    def database():
        with Session(pg_engine) as session:
            yield session

    app.dependency_overrides[get_db] = database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def new_phone() -> str:
    # Números aleatorios para que la suite se pueda repetir sobre la misma base.
    return "9" + "".join(random.choice("0123456789") for _ in range(8))


def login(client, phone):
    response = client.post("/api/v1/auth/phone-login", json={"phone": phone})
    assert response.status_code == 200, response.text
    body = response.json()
    return body, {"Authorization": f"Bearer {body['session_token']}"}


def idem(headers):
    return {**headers, "Idempotency-Key": uuid.uuid4().hex}


def wallets(client, headers):
    response = client.get("/api/v1/wallets", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def by_role(listing, role):
    return next(w for w in listing["items"] if w["role"] == role)


def fund(client, headers, wallet_id, amount):
    response = client.post(
        "/api/v1/demo/incoming-yapes",
        headers=idem(headers),
        json={"to_wallet_id": wallet_id, "amount": amount, "from_name": "Cliente prueba"},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ----------------------------------------------------------------------------- login


def test_phone_login_validates_number(client):
    response = client.post("/api/v1/auth/phone-login", json={"phone": "812345678"})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PHONE"
    assert "9 dígitos" in response.json()["message"]


def test_same_phone_same_account_and_random_data_per_number(client):
    phone = new_phone()
    first, headers = login(client, phone)
    assert first["is_new"] is True
    assert first["phone_masked"] == f"*** *** {phone[-3:]}"
    listing = wallets(client, headers)
    roles = [w["role"] for w in listing["items"]]
    assert roles == ["PRINCIPAL", "BUSINESS", "SAVINGS"]
    assert all(Decimal(w["balance"]) > 0 for w in listing["items"])
    assert Decimal(listing["total"]) == sum(Decimal(w["balance"]) for w in listing["items"])

    movements = client.get("/api/v1/movements", headers=headers).json()["items"]
    assert len(movements) == 9  # saldos iniciales ocultos; solo movimientos de la demo
    assert {m["direction"] for m in movements} == {"IN", "OUT", "TRANSFER"}

    again, headers_again = login(client, phone)
    assert again["is_new"] is False
    assert again["business_id"] == first["business_id"]
    assert wallets(client, headers_again)["items"] == listing["items"]

    _, other_headers = login(client, new_phone())
    other = wallets(client, other_headers)
    assert [w["balance"] for w in other["items"]] != [w["balance"] for w in listing["items"]]


def test_seed_is_deterministic_per_seed(db):
    from app.modules.business.models import Business
    from app.modules.identity.models import User
    from app.modules.ledger import service as ledger
    from app.modules.wallets import service

    def seeded(seed):
        user = User(display_name="Semilla")
        db.add(user)
        db.flush()
        business = Business(owner_id=user.id, name="Semilla", environment="DEMO")
        db.add(business)
        db.flush()
        ledger.ensure_accounts(db, business.id)
        service.seed_demo_data(db, business.id, "DEMO", seed)
        db.flush()
        items = service.active_wallets(db, business.id)
        balances = service.balances_by_account(db, [w.account_id for w in items])
        return [balances[w.account_id] for w in items]

    assert seeded("misma-semilla") == seeded("misma-semilla")
    assert seeded("misma-semilla") != seeded("otra-semilla")
    db.rollback()


def test_logout_and_me(client):
    phone = new_phone()
    body, headers = login(client, phone)
    me = client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["phone_masked"] == f"*** *** {phone[-3:]}"
    assert me.json()["business_id"] == body["business_id"]
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/wallets", headers=headers).status_code == 401


# ----------------------------------------------------------------------------- billeteras


def test_create_wallet_validations(client):
    _, headers = login(client, new_phone())
    short = client.post(
        "/api/v1/wallets", headers=idem(headers), json={"name": "ab", "purpose": "BUSINESS"}
    )
    assert short.status_code == 422 and short.json()["code"] == "NAME_INVALID"
    dup = client.post(
        "/api/v1/wallets",
        headers=idem(headers),
        json={"name": "  ahorro   vacaciones ", "purpose": "SAVINGS"},
    )
    assert dup.status_code == 409 and dup.json()["code"] == "NAME_TAKEN"
    created = client.post(
        "/api/v1/wallets",
        headers=idem(headers),
        json={"name": "Mi Bodega", "purpose": "BUSINESS", "icon": "☕", "color": "teal"},
    )
    assert created.status_code == 201, created.text
    wallet = created.json()
    assert (
        wallet["role"] == "CUSTOM" and wallet["balance"] == "0.00" and wallet["is_business"] is True
    )
    assert any(w["id"] == wallet["id"] for w in wallets(client, headers)["items"])


def test_archive_wallet_rules(client):
    _, headers = login(client, new_phone())
    listing = wallets(client, headers)
    principal = by_role(listing, "PRINCIPAL")
    savings = by_role(listing, "SAVINGS")
    total = Decimal(listing["total"])

    locked = client.delete(f"/api/v1/wallets/{principal['id']}", headers=idem(headers))
    assert locked.status_code == 409 and locked.json()["code"] == "PRIMARY_LOCKED"

    needs = client.delete(f"/api/v1/wallets/{savings['id']}", headers=idem(headers))
    assert needs.status_code == 409 and needs.json()["code"] == "BALANCE_REQUIRES_DESTINATION"

    done = client.delete(
        f"/api/v1/wallets/{savings['id']}?move_to_wallet_id={principal['id']}",
        headers=idem(headers),
    )
    assert done.status_code == 200, done.text
    assert done.json()["moved_amount"] == savings["balance"]

    after = wallets(client, headers)
    assert [w["role"] for w in after["items"]] == ["PRINCIPAL", "BUSINESS"]
    assert Decimal(after["total"]) == total
    assert Decimal(by_role(after, "PRINCIPAL")["balance"]) == Decimal(
        principal["balance"]
    ) + Decimal(savings["balance"])
    # Los movimientos que eran solo de la billetera archivada ya no se listan.
    titles = [m["title"] for m in client.get("/api/v1/movements", headers=headers).json()["items"]]
    assert "Aporte a Vacaciones" in titles  # también es de la Principal: se mantiene
    assert any(t.startswith("Saldo de Ahorro Vacaciones") for t in titles)


# ----------------------------------------------------------------------------- transferencias


def test_wallet_transfer(client):
    _, headers = login(client, new_phone())
    listing = wallets(client, headers)
    business = by_role(listing, "BUSINESS")
    savings = by_role(listing, "SAVINGS")

    same = client.post(
        "/api/v1/wallet-transfers",
        headers=idem(headers),
        json={"from_wallet_id": business["id"], "to_wallet_id": business["id"], "amount": "1.00"},
    )
    assert same.status_code == 422 and same.json()["code"] == "SAME_WALLET"

    too_much = client.post(
        "/api/v1/wallet-transfers",
        headers=idem(headers),
        json={
            "from_wallet_id": business["id"],
            "to_wallet_id": savings["id"],
            "amount": "999999.00",
        },
    )
    assert too_much.status_code == 409 and too_much.json()["code"] == "INSUFFICIENT_BALANCE"
    assert "Disponible" in too_much.json()["message"]

    long_note = client.post(
        "/api/v1/wallet-transfers",
        headers=idem(headers),
        json={
            "from_wallet_id": business["id"],
            "to_wallet_id": savings["id"],
            "amount": "1.00",
            "note": "x" * 41,
        },
    )
    assert long_note.status_code == 422

    ok = client.post(
        "/api/v1/wallet-transfers",
        headers=idem(headers),
        json={
            "from_wallet_id": business["id"],
            "to_wallet_id": savings["id"],
            "amount": "10.50",
            "note": "Para el mes",
        },
    )
    assert ok.status_code == 201, ok.text
    movement = ok.json()["movement"]
    assert movement["direction"] == "TRANSFER" and movement["note"] == "Para el mes"
    assert (
        movement["from_wallet"]["id"] == business["id"]
        and movement["to_wallet"]["id"] == savings["id"]
    )
    after = ok.json()["wallets"]
    assert Decimal(by_role(after, "BUSINESS")["balance"]) == Decimal(business["balance"]) - Decimal(
        "10.50"
    )
    assert Decimal(by_role(after, "SAVINGS")["balance"]) == Decimal(savings["balance"]) + Decimal(
        "10.50"
    )


# ----------------------------------------------------------------------------- yapeos


def test_yapeo_rules_receipt_and_idempotency(client):
    _, headers = login(client, new_phone())
    listing = wallets(client, headers)
    business = by_role(listing, "BUSINESS")
    savings = by_role(listing, "SAVINGS")

    cat_on_savings = client.post(
        "/api/v1/yapeos",
        headers=idem(headers),
        json={
            "from_wallet_id": savings["id"],
            "amount": "5.00",
            "counterparty": {"type": "CONTACT", "name": "Carlos Ruiz"},
            "category": "RESTOCK",
        },
    )
    assert (
        cat_on_savings.status_code == 422
        and cat_on_savings.json()["code"] == "CATEGORY_NOT_ALLOWED"
    )

    over = client.post(
        "/api/v1/yapeos",
        headers=idem(headers),
        json={
            "from_wallet_id": business["id"],
            "amount": "500.01",
            "counterparty": {"type": "CONTACT", "name": "X"},
        },
    )
    assert over.status_code == 422 and over.json()["code"] == "PER_PAYMENT_LIMIT"

    request_headers = idem(headers)
    payload = {
        "from_wallet_id": business["id"],
        "amount": "12.05",
        "counterparty": {"type": "PHONE", "name": "Celular 987 654 321", "phone": "987654321"},
        "category": "RESTOCK",
    }
    first = client.post("/api/v1/yapeos", headers=request_headers, json=payload)
    assert first.status_code == 201, first.text
    receipt = first.json()["movement"]
    assert receipt["direction"] == "OUT" and receipt["amount"] == "-12.05"
    assert receipt["kind"] == "BUSINESS_PAYMENT"
    assert receipt["category_label"] == "📦 Para volver a surtir"
    assert receipt["counterparty_phone_masked"] == "*** *** 321"
    assert len(receipt["operation_number"]) == 8 and len(receipt["security_code"]) == 3
    # Reintento con la misma clave: misma constancia, sin cobrar dos veces.
    repeat = client.post("/api/v1/yapeos", headers=request_headers, json=payload)
    assert repeat.json()["movement"]["operation_number"] == receipt["operation_number"]
    after = wallets(client, headers)
    assert Decimal(by_role(after, "BUSINESS")["balance"]) == Decimal(business["balance"]) - Decimal(
        "12.05"
    )

    detail = client.get(f"/api/v1/movements/{receipt['id']}", headers=headers)
    assert (
        detail.status_code == 200
        and detail.json()["operation_number"] == receipt["operation_number"]
    )

    family = client.post(
        "/api/v1/yapeos",
        headers=idem(headers),
        json={
            "from_wallet_id": business["id"],
            "amount": "1.00",
            "counterparty": {"type": "CONTACT", "name": "Mamá"},
            "category": "FAMILY",
        },
    )
    assert family.json()["movement"]["kind"] == "HOUSEHOLD_WITHDRAWAL"


def test_daily_limit(client):
    _, headers = login(client, new_phone())
    principal = by_role(wallets(client, headers), "PRINCIPAL")
    fund(client, headers, principal["id"], "2500.00")
    for _ in range(4):
        ok = client.post(
            "/api/v1/yapeos",
            headers=idem(headers),
            json={
                "from_wallet_id": principal["id"],
                "amount": "490.00",
                "counterparty": {"type": "CONTACT", "name": "A"},
            },
        )
        assert ok.status_code == 201, ok.text
    blocked = client.post(
        "/api/v1/yapeos",
        headers=idem(headers),
        json={
            "from_wallet_id": principal["id"],
            "amount": "50.00",
            "counterparty": {"type": "CONTACT", "name": "A"},
        },
    )
    assert blocked.status_code == 422 and blocked.json()["code"] == "DAILY_LIMIT"
    assert blocked.json()["details"]["remaining"] == "40.00"


# ----------------------------------------------------------------------------- movimientos


def test_movements_filter_and_incoming(client):
    _, headers = login(client, new_phone())
    listing = wallets(client, headers)
    savings = by_role(listing, "SAVINGS")
    incoming = fund(client, headers, savings["id"], "33.00")["movement"]
    assert incoming["direction"] == "IN" and incoming["title"] == "Yape de Cliente prueba"
    only_savings = client.get(
        f"/api/v1/movements?wallet_id={savings['id']}", headers=headers
    ).json()["items"]
    assert only_savings[0]["id"] == incoming["id"]
    assert all(any(w["id"] == savings["id"] for w in m["wallets"]) for m in only_savings)
    page = client.get("/api/v1/movements?limit=2", headers=headers).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = client.get(
        f"/api/v1/movements?limit=50&cursor={page['next_cursor']}", headers=headers
    ).json()
    assert {m["id"] for m in rest["items"]}.isdisjoint({m["id"] for m in page["items"]})
