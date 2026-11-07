"""Pruebas de elegibilidad ilustrativa de ahorro y crédito."""

from __future__ import annotations

from decimal import Decimal

from app.modules.opportunities.domain import (
    ACTIVE_ALERT,
    ACTIVE_CREDIT,
    CONSENT_MISSING,
    DEBT_UNKNOWN,
    INSUFFICIENT_STABLE_WEEKS,
    NON_POSITIVE_FLOW,
    OpportunityInput,
    evaluate,
)


def _input(**overrides) -> OpportunityInput:
    base = {
        "stable_weeks": 8,
        "required_weeks": 8,
        "active_alerts": False,
        "invitations_consent": True,
        "coverage_ok": True,
        "debt_status": "NONE",
        "credit_active": False,
        "last_flows": [Decimal("600.00")] * 8,
        "installment_ratio": Decimal("0.20"),
    }
    base.update(overrides)
    return OpportunityInput(**base)


def test_credito_elegible_con_cap_del_20_por_ciento() -> None:
    result = evaluate(_input())
    assert result.eligible is True
    assert result.product_type == "CREDIT"
    assert result.weekly_installment_cap == Decimal("120.00")
    assert result.reasons == []


def test_ahorro_elegible_si_deuda_es_desconocida() -> None:
    result = evaluate(_input(debt_status="UNKNOWN"))
    assert result.eligible is True
    assert result.product_type == "SAVINGS"
    assert result.reasons == []


def test_sin_consentimiento_bloquea_todo() -> None:
    result = evaluate(_input(invitations_consent=False))
    assert result.eligible is False
    assert CONSENT_MISSING in result.reasons


def test_alerta_activa_bloquea_invitacion() -> None:
    result = evaluate(_input(active_alerts=True))
    assert result.eligible is False
    assert ACTIVE_ALERT in result.reasons


def test_semanas_estables_insuficientes() -> None:
    result = evaluate(_input(stable_weeks=5))
    assert result.eligible is False
    assert INSUFFICIENT_STABLE_WEEKS in result.reasons


def test_deuda_conocida_bloquea_credito_pero_no_ahorro() -> None:
    result = evaluate(_input(debt_status="KNOWN_DEBT"))
    assert result.product_type == "SAVINGS"
    assert ACTIVE_CREDIT not in result.reasons


def test_credito_activo_bloquea_credito_pero_no_ahorro() -> None:
    result = evaluate(_input(credit_active=True))
    assert result.product_type == "SAVINGS"
    assert ACTIVE_CREDIT not in result.reasons


def test_flujo_no_positivo_bloquea_credito() -> None:
    flows = [Decimal("600.00")] * 7 + [Decimal("0.00")]
    result = evaluate(_input(last_flows=flows))
    assert result.product_type == "SAVINGS"
    assert NON_POSITIVE_FLOW not in result.reasons


def test_motivo_deuda_desconocida_aparece_si_no_hay_ahorro() -> None:
    result = evaluate(_input(debt_status="UNKNOWN", stable_weeks=2))
    assert result.eligible is False
    assert DEBT_UNKNOWN in result.reasons
