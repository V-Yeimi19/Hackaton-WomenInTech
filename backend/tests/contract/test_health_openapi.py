"""Contrato HTTP mínimo: salud y OpenAPI sin tocar la base de datos."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openapi_versionado_coincide_con_la_api() -> None:
    import json
    from pathlib import Path

    contract = Path(__file__).resolve().parents[3] / "docs/contracts/openapi.json"
    assert json.loads(contract.read_text(encoding="utf-8")) == app.openapi()


def test_health_live_no_expone_datos_internos() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "mica-api"
    assert "database_url" not in body
    assert response.headers["X-Correlation-ID"]


def test_openapi_expone_rutas_p0() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/demo/sessions" in paths
    assert "/api/v1/business/activation" in paths
    assert "/api/v1/payments" in paths
    assert "/api/v1/reports/preview" in paths
    assert "/api/v1/webhooks/twilio/whatsapp" in paths
    assert "/health/ready" in paths


def test_escritura_sin_idempotencia_falla_antes_de_tocar_bd() -> None:
    # Sin sesión el contrato devuelve 401; sin Idempotency-Key no debe existir
    # efecto financiero. La comprobación de sesión ocurre primero.
    response = client.post("/api/v1/payments", json={"amount": "10.00"})
    assert response.status_code in (401, 403)
    body = response.json()
    assert body["code"] in ("UNAUTHENTICATED", "CSRF_INVALID")
    assert body["correlation_id"]
