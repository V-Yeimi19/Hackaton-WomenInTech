"""Carga local reproducible: python -m tests.benchmark_backend.

Requiere MICA_TEST_DATABASE_URL migrada. Genera solo datos sintéticos nuevos.
No mide TLS, red móvil, navegador ni Twilio real.
"""

import json
import os
import platform
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, sign_simulator_payload
from app.db.base import utcnow
from app.db.session import get_db
from app.main import app
from app.modules.business.models import Business
from app.modules.identity.models import Session as LoginSession
from app.modules.identity.models import User
from app.modules.ledger.models import LedgerEntry, Transaction
from app.modules.ledger.service import ensure_accounts


def main():
    engine = create_engine(os.environ["MICA_TEST_DATABASE_URL"], pool_size=20, max_overflow=5)
    with Session(engine) as db:
        user = User(display_name="Carga sintética")
        db.add(user)
        db.flush()
        business = Business(owner_id=user.id, name="Carga 10000", environment="DEMO")
        db.add(business)
        db.flush()
        accounts = ensure_accounts(db, business.id)
        tokens = [uuid.uuid4().hex for _ in range(20)]
        for token in tokens:
            db.add(
                LoginSession(
                    user_id=user.id,
                    token_hash=hash_token(token),
                    csrf_token=token,
                    expires_at=utcnow() + timedelta(hours=1),
                )
            )
        rows, entries = [], []
        for _ in range(10000):
            tx = uuid.uuid4()
            rows.append(
                dict(
                    id=tx,
                    business_id=business.id,
                    kind="SALE",
                    amount=Decimal("1.00"),
                    medium="DIGITAL",
                    currency="PEN",
                    status="POSTED",
                    source="SIMULATED",
                    environment="DEMO",
                    classification_source="EXPLICIT_ACTION",
                    occurred_at=utcnow() - timedelta(seconds=1),
                    confirmed_at=utcnow(),
                )
            )
            for kind, delta in (("BUSINESS_DIGITAL", "1.00"), ("EXTERNAL_CLEARING", "-1.00")):
                entries.append(
                    dict(
                        id=uuid.uuid4(),
                        business_id=business.id,
                        transaction_id=tx,
                        account_id=accounts[kind].id,
                        delta=Decimal(delta),
                    )
                )
        db.execute(insert(Transaction), rows)
        db.execute(insert(LedgerEntry), entries)
        db.commit()
        business_id = str(business.id)

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    get_settings().process_inbox_inline = False
    timings = {"reads_ms": [], "webhook_ms": [], "report_ms": []}
    with TestClient(app) as client:

        def read(index):
            started = time.perf_counter()
            response = client.get(
                "/api/v1/business/balances",
                headers={"Authorization": f"Bearer {tokens[index % 20]}"},
            )
            assert response.status_code == 200, response.text
            return (time.perf_counter() - started) * 1000

        with ThreadPoolExecutor(max_workers=20) as pool:
            timings["reads_ms"] = list(pool.map(read, range(200)))
        for _ in range(20):
            event = {
                "schema_version": "1.0",
                "event_id": uuid.uuid4().hex,
                "event_type": "transaction.confirmed",
                "external_transaction_id": uuid.uuid4().hex,
                "business_reference": business_id,
                "kind": "SALE",
                "amount": "1.00",
                "currency": "PEN",
                "occurred_at": utcnow().isoformat(),
                "source": "SIMULATED",
            }
            raw = json.dumps(event).encode()
            timestamp = str(int(time.time()))
            started = time.perf_counter()
            response = client.post(
                "/api/v1/webhooks/simulator/transactions",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-Mica-Timestamp": timestamp,
                    "X-Mica-Signature": sign_simulator_payload(timestamp, raw),
                },
            )
            assert response.status_code == 202, response.text
            timings["webhook_ms"].append((time.perf_counter() - started) * 1000)
        for _ in range(10):
            started = time.perf_counter()
            response = client.post(
                "/api/v1/reports/preview",
                json={"kind": "PRELIMINARY"},
                headers={"Authorization": f"Bearer {tokens[0]}"},
            )
            assert response.status_code == 200, response.text
            timings["report_ms"].append((time.perf_counter() - started) * 1000)
    app.dependency_overrides.clear()
    print(
        json.dumps(
            {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "transactions": 10000,
                "sessions": 20,
                "concurrent_readers": 20,
                "p95_ms": {
                    key: round(sorted(values)[int(len(values) * 0.95) - 1], 2)
                    for key, values in timings.items()
                },
            },
            indent=2,
        )
    )
    engine.dispose()


if __name__ == "__main__":
    main()
