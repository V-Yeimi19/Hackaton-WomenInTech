"""Reglas puras de las tres alertas."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.shared.money import money_str

EXCESS_WITHDRAWAL = "EXCESS_WITHDRAWAL"
SALES_DROP = "SALES_DROP"
PAYMENT_SHORTFALL = "PAYMENT_SHORTFALL"

PRIORITY = {
    PAYMENT_SHORTFALL: 0,
    EXCESS_WITHDRAWAL: 1,
    SALES_DROP: 2,
}


@dataclass
class AlertData:
    code: str
    severity: str
    message: str
    evidence: dict = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return PRIORITY.get(self.code, 99)


@dataclass
class AlertInput:
    sales: Decimal
    operating_flow: Decimal
    withdrawals: Decimal
    pending_classifications: int
    previous_sales: list[Decimal] = field(default_factory=list)
    shortfall_by_medium: dict[str, Decimal] = field(default_factory=dict)
    shortfall_details: list[dict] = field(default_factory=list)
    sales_drop_threshold: Decimal = Decimal("0.30")
    capture_failures: bool = False


def evaluate_alerts(data: AlertInput) -> list[AlertData]:
    alerts: list[AlertData] = []

    # PAYMENT_SHORTFALL: saldo del medio < compromisos en 7 días del mismo medio.
    shortfalls = {
        medium: amount
        for medium, amount in (data.shortfall_by_medium or {}).items()
        if amount is not None and amount > 0
    }
    if shortfalls:
        detail = ", ".join(
            f"{medium}: S/{money_str(value)}" for medium, value in shortfalls.items()
        )
        if data.shortfall_details:
            first = data.shortfall_details[0]
            message = (
                f"Tienes un compromiso próximo: «{first.get('label', 'pago')}» vence el "
                f"{str(first.get('due_at', ''))[:10]} por S/{first.get('amount', '0.00')}. "
                f"Te faltan S/{first.get('shortfall', '0.00')} en el medio "
                f"{'digital' if first.get('medium') == 'DIGITAL' else 'efectivo declarado'}."
            )
        else:
            message = (
                f"Tienes un compromiso próximo y te falta dinero en el medio de pago ({detail})."
            )
        alerts.append(
            AlertData(
                code=PAYMENT_SHORTFALL,
                severity="HIGH",
                message=message,
                evidence={
                    "shortfall_by_medium": {k: money_str(v) for k, v in shortfalls.items()},
                    "commitments": data.shortfall_details,
                },
            )
        )

    # EXCESS_WITHDRAWAL: R > max(F, 0), solo con clasificación resuelta.
    if data.pending_classifications == 0:
        excess = data.withdrawals > max(data.operating_flow, Decimal("0.00"))
        if excess:
            alerts.append(
                AlertData(
                    code=EXCESS_WITHDRAWAL,
                    severity="MEDIUM",
                    message=(
                        "Sacaste más de lo que quedó de tus cobros después de pagar el negocio. "
                        "No es una afirmación sobre tu utilidad."
                    ),
                    evidence={
                        "withdrawals": money_str(data.withdrawals),
                        "operating_flow": money_str(data.operating_flow),
                    },
                )
            )

    # SALES_DROP: V_actual < promedio de 4 semanas previas × (1 - umbral).
    if len(data.previous_sales) >= 4 and not data.capture_failures:
        last_four = data.previous_sales[:4]
        if all(value is not None for value in last_four):
            average = sum(last_four, Decimal("0.00")) / Decimal(len(last_four))
            threshold_value = average * (Decimal("1.00") - data.sales_drop_threshold)
            if average > 0 and data.sales < threshold_value:
                alerts.append(
                    AlertData(
                        code=SALES_DROP,
                        severity="MEDIUM",
                        message="Tus cobros registrados bajaron frente a tu promedio de las últimas cuatro semanas.",
                        evidence={
                            "current_sales": money_str(data.sales),
                            "previous_average": money_str(average),
                            "threshold": money_str(threshold_value),
                        },
                    )
                )

    alerts.sort(key=lambda alert: alert.priority)
    return alerts


def primary_alert(alerts: list[AlertData]) -> AlertData | None:
    return alerts[0] if alerts else None
