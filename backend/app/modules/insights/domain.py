"""Cálculos puros de métricas y periodos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.shared.money import money_str


@dataclass
class Metrics:
    sales: Decimal = Decimal("0.00")
    digital_sales: Decimal = Decimal("0.00")
    cash_sales: Decimal = Decimal("0.00")
    payments: Decimal = Decimal("0.00")
    withdrawals: Decimal = Decimal("0.00")
    contributions: Decimal = Decimal("0.00")
    business_digital_balance: Decimal = Decimal("0.00")
    household_digital_balance: Decimal = Decimal("0.00")
    declared_cash_balance: Decimal = Decimal("0.00")
    pending_classifications: int = 0
    coverage_status: str = "RECORDED_ONLY"

    @property
    def operating_flow(self) -> Decimal:
        return (self.sales - self.payments).quantize(Decimal("0.01"))

    @property
    def variation(self) -> Decimal:
        return (self.sales - self.payments - self.withdrawals + self.contributions).quantize(
            Decimal("0.01")
        )

    def to_public_dict(self) -> dict[str, str]:
        return {
            "sales_collected": money_str(self.sales),
            "digital_sales": money_str(self.digital_sales),
            "cash_sales": money_str(self.cash_sales),
            "business_payments": money_str(self.payments),
            "household_withdrawals": money_str(self.withdrawals),
            "owner_contributions": money_str(self.contributions),
            "operating_cash_flow": money_str(self.operating_flow),
            "registered_variation": money_str(self.variation),
            "business_digital_balance": money_str(self.business_digital_balance),
            "household_digital_balance": money_str(self.household_digital_balance),
            "declared_cash_balance": money_str(self.declared_cash_balance),
        }


def comparison_pct(current: Decimal, previous: Decimal) -> str | None:
    """(actual - anterior) / anterior × 100 solo si el denominador es > 0."""
    if previous <= 0:
        return None
    value = ((current - previous) / previous * Decimal(100)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return f"{value}"


def comparison_label(current: Decimal, previous: Decimal) -> str:
    value = comparison_pct(current, previous)
    if value is None:
        return "sin base suficiente para comparar"
    if value.startswith("-"):
        return f"{value}% menos que la semana anterior"
    return f"{value}% más que la semana anterior"


def opportunity_installment_cap(flows: list[Decimal], ratio: Decimal) -> Decimal | None:
    positive = [flow for flow in flows if flow > 0]
    if len(positive) < len(flows) or not positive:
        return None
    return (min(positive) * ratio).quantize(Decimal("0.01"))


def coverage_dict(metrics: Metrics, contains_simulated: bool = True) -> dict:
    return {
        "coverage": metrics.coverage_status,
        "pending_classifications": metrics.pending_classifications,
        "contains_simulated_data": contains_simulated,
        "profit_calculated": False,
    }
