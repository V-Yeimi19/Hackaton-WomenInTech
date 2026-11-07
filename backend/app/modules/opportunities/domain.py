"""Elegibilidad ilustrativa de ahorro/crédito (reglas determinísticas)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.modules.insights.domain import opportunity_installment_cap

ACTIVE_ALERT = "ACTIVE_ALERT"
INSUFFICIENT_STABLE_WEEKS = "INSUFFICIENT_STABLE_WEEKS"
CONSENT_MISSING = "CONSENT_MISSING"
DEBT_UNKNOWN = "DEBT_UNKNOWN"
ACTIVE_CREDIT = "ACTIVE_CREDIT"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
NON_POSITIVE_FLOW = "NON_POSITIVE_FLOW"


@dataclass
class OpportunityInput:
    stable_weeks: int
    required_weeks: int
    active_alerts: bool
    invitations_consent: bool
    coverage_ok: bool = True
    debt_status: str = "UNKNOWN"
    credit_active: bool = False
    last_flows: list[Decimal] = field(default_factory=list)
    installment_ratio: Decimal = Decimal("0.20")


@dataclass
class OpportunityResult:
    eligible: bool
    product_type: str | None
    reasons: list[str]
    stable_weeks: int
    weekly_installment_cap: Decimal | None = None


def evaluate(inputs: OpportunityInput) -> OpportunityResult:
    reasons: list[str] = []

    if not inputs.invitations_consent:
        reasons.append(CONSENT_MISSING)
    if not inputs.coverage_ok:
        reasons.append(INSUFFICIENT_DATA)
    if inputs.active_alerts:
        reasons.append(ACTIVE_ALERT)
    if inputs.stable_weeks < inputs.required_weeks:
        reasons.append(INSUFFICIENT_STABLE_WEEKS)

    savings_eligible = not reasons

    credit_reasons = list(reasons)
    # RN-21: el crédito exige deuda del escenario *conocida* y sin deuda activa.
    # Solo ``NONE`` acredita esa condición; ``UNKNOWN`` y ``KNOWN_DEBT`` bloquean.
    if inputs.debt_status != "NONE":
        credit_reasons.append(DEBT_UNKNOWN)
    if inputs.credit_active:
        credit_reasons.append(ACTIVE_CREDIT)
    if not inputs.last_flows or any(flow <= 0 for flow in inputs.last_flows):
        credit_reasons.append(NON_POSITIVE_FLOW)

    credit_cap = opportunity_installment_cap(inputs.last_flows, inputs.installment_ratio)
    credit_eligible = not credit_reasons and credit_cap is not None

    if credit_eligible:
        return OpportunityResult(
            eligible=True,
            product_type="CREDIT",
            reasons=[],
            stable_weeks=inputs.stable_weeks,
            weekly_installment_cap=credit_cap,
        )
    if savings_eligible:
        return OpportunityResult(
            eligible=True,
            product_type="SAVINGS",
            reasons=[],
            stable_weeks=inputs.stable_weeks,
        )

    # Mostrar el bloqueo más relevante de crédito cuando no hay elegibilidad.
    return OpportunityResult(
        eligible=False,
        product_type=None,
        reasons=credit_reasons,
        stable_weeks=inputs.stable_weeks,
    )
