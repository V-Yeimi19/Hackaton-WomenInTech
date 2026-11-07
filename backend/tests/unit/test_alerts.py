"""Pruebas puras de las tres alertas y su prioridad."""

from __future__ import annotations

from decimal import Decimal

from app.modules.alerts.domain import (
    EXCESS_WITHDRAWAL,
    PAYMENT_SHORTFALL,
    PRIORITY,
    SALES_DROP,
    AlertInput,
    evaluate_alerts,
)


def _input(**overrides) -> AlertInput:
    base = {
        "sales": Decimal("1500.00"),
        "operating_flow": Decimal("700.00"),
        "withdrawals": Decimal("600.00"),
        "pending_classifications": 0,
    }
    base.update(overrides)
    return AlertInput(**base)


def test_payment_shortfall_por_medio_y_detalle() -> None:
    alerts = evaluate_alerts(
        _input(
            shortfall_by_medium={"DIGITAL": Decimal("1400.00")},
            shortfall_details=[
                {
                    "commitment_id": "c1",
                    "label": "Proveedor mayorista",
                    "due_at": "2026-11-09T10:00:00+00:00",
                    "amount": "1500.00",
                    "medium": "DIGITAL",
                    "shortfall": "1400.00",
                }
            ],
        )
    )
    assert [alert.code for alert in alerts] == [PAYMENT_SHORTFALL]
    assert alerts[0].severity == "HIGH"
    assert "1400.00" in alerts[0].message
    assert alerts[0].evidence["shortfall_by_medium"]["DIGITAL"] == "1400.00"
    assert alerts[0].evidence["commitments"][0]["label"] == "Proveedor mayorista"


def test_no_alerta_de_retiro_si_hay_clasificacion_pendiente() -> None:
    alerts = evaluate_alerts(_input(withdrawals=Decimal("900.00"), pending_classifications=1))
    assert EXCESS_WITHDRAWAL not in [alert.code for alert in alerts]


def test_alerta_de_retiro_excesivo() -> None:
    alerts = evaluate_alerts(_input(withdrawals=Decimal("800.00")))
    assert [alert.code for alert in alerts] == [EXCESS_WITHDRAWAL]


def test_sin_alerta_de_retiro_cuando_es_igual_al_flujo() -> None:
    alerts = evaluate_alerts(_input(withdrawals=Decimal("700.00")))
    assert alerts == []


def test_sales_drop_con_promedio_de_cuatro_semanas() -> None:
    alerts = evaluate_alerts(
        _input(
            sales=Decimal("600.00"),
            operating_flow=Decimal("600.00"),
            withdrawals=Decimal("0.00"),
            previous_sales=[Decimal("1000.00")] * 4,
            sales_drop_threshold=Decimal("0.30"),
        )
    )
    assert [alert.code for alert in alerts] == [SALES_DROP]
    assert alerts[0].evidence["previous_average"] == "1000.00"
    assert alerts[0].evidence["threshold"] == "700.00"


def test_sales_drop_no_se_dispara_sin_cuatro_semanas() -> None:
    alerts = evaluate_alerts(
        _input(
            sales=Decimal("1.00"),
            previous_sales=[Decimal("1000.00")] * 3,
        )
    )
    assert SALES_DROP not in [alert.code for alert in alerts]


def test_prioridad_pago_antes_que_retiro_y_ventas() -> None:
    alerts = evaluate_alerts(
        _input(
            sales=Decimal("500.00"),
            operating_flow=Decimal("100.00"),
            withdrawals=Decimal("200.00"),
            previous_sales=[Decimal("1000.00")] * 4,
            shortfall_by_medium={"CASH": Decimal("50.00")},
        )
    )
    assert [alert.code for alert in alerts] == [
        PAYMENT_SHORTFALL,
        EXCESS_WITHDRAWAL,
        SALES_DROP,
    ]
    assert [alert.priority for alert in alerts] == sorted(
        [PRIORITY[alert.code] for alert in alerts]
    )
