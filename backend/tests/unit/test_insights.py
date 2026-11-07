"""Pruebas de cálculos puros de reportes y periodos."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.modules.insights.domain import (
    Metrics,
    comparison_label,
    comparison_pct,
    coverage_dict,
    opportunity_installment_cap,
)
from app.modules.insights.service import resolve_period
from app.shared.clock import week_end, week_start


def test_metrics_operating_flow_y_variacion() -> None:
    metrics = Metrics(
        sales=Decimal("1500.00"),
        payments=Decimal("800.00"),
        withdrawals=Decimal("600.00"),
        contributions=Decimal("300.00"),
    )
    assert metrics.operating_flow == Decimal("700.00")
    assert metrics.variation == Decimal("400.00")
    public = metrics.to_public_dict()
    assert public["sales_collected"] == "1500.00"
    assert public["operating_cash_flow"] == "700.00"
    assert public["registered_variation"] == "400.00"


def test_comparacion_sin_base_si_anterior_es_cero() -> None:
    assert comparison_pct(Decimal("100.00"), Decimal("0.00")) is None
    assert comparison_label(Decimal("100.00"), Decimal("0.00")) == (
        "sin base suficiente para comparar"
    )


def test_comparacion_porcentual() -> None:
    assert comparison_pct(Decimal("800.00"), Decimal("1000.00")) == "-20.0"
    assert comparison_label(Decimal("1200.00"), Decimal("1000.00")) == (
        "20.0% más que la semana anterior"
    )


def test_cap_de_cuota_requiere_flujos_positivos() -> None:
    flows = [Decimal("600.00")] * 8
    assert opportunity_installment_cap(flows, Decimal("0.20")) == Decimal("120.00")
    assert (
        opportunity_installment_cap([Decimal("600.00"), Decimal("0.00")], Decimal("0.20")) is None
    )
    assert opportunity_installment_cap([], Decimal("0.20")) is None


def test_coverage_dict_no_calcula_utilidad() -> None:
    data = coverage_dict(Metrics(sales=Decimal("10.00")))
    assert data["profit_calculated"] is False
    assert data["contains_simulated_data"] is True


def test_semana_en_america_lima() -> None:
    saturday_lima = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)
    start = week_start(saturday_lima)
    assert start.isoformat() == "2026-11-02T05:00:00+00:00"
    assert week_end(saturday_lima).isoformat() == "2026-11-09T05:00:00+00:00"


def test_auto_consolida_lunes_temprano_y_preliminar_resto() -> None:
    monday_early = datetime(2026, 11, 9, 5, 5, tzinfo=UTC)
    start, end, kind = resolve_period(monday_early)
    assert kind == "WEEKLY_FINAL"
    assert start.isoformat() == "2026-11-02T05:00:00+00:00"
    assert end.isoformat() == "2026-11-09T05:00:00+00:00"

    tuesday = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
    start, end, kind = resolve_period(tuesday)
    assert kind == "PRELIMINARY"
    assert start.isoformat() == "2026-11-09T05:00:00+00:00"
    assert end.isoformat() == "2026-11-16T05:00:00+00:00"


def test_kind_explicito_prevalece() -> None:
    tuesday = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
    start, _, kind = resolve_period(tuesday, "WEEKLY_FINAL")
    assert kind == "WEEKLY_FINAL"
    assert start.isoformat() == "2026-11-02T05:00:00+00:00"
