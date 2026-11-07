"""Agregados semanales, snapshots de reporte, alertas y oportunidades.

El motor es determinístico: los saldos salen de asientos, las métricas de
operaciones y las decisiones de reglas versionadas. No participa un LLM.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.integrations.narration_template import render_report
from app.modules.alerts import service as alerts_service
from app.modules.alerts.domain import PRIORITY, AlertData, AlertInput, evaluate_alerts
from app.modules.business.models import Business
from app.modules.classification.models import ClassificationRequest
from app.modules.commitments import service as commitments_service
from app.modules.consents import service as consents_service
from app.modules.consents.models import Preference
from app.modules.education.domain import choose_advice
from app.modules.insights.domain import (
    Metrics,
    comparison_label,
    coverage_dict,
)
from app.modules.insights.models import WeeklyFact, WeeklyReport
from app.modules.ledger import domain as ledger_domain
from app.modules.ledger.models import Account, LedgerEntry, Transaction
from app.modules.ledger.service import _lock_display_accounts
from app.modules.messaging.models import InboundEvent
from app.modules.opportunities import service as opportunities_service
from app.modules.opportunities.domain import OpportunityInput, evaluate
from app.shared.clock import week_start
from app.shared.money import money_str

settings = get_settings()
ZERO = Decimal("0.00")
WEEK = timedelta(days=7)


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def _effective_end(start: datetime, end: datetime, cutoff: datetime) -> datetime:
    return min(end, cutoff)


def compute_metrics(
    db: Session,
    business_id: uuid.UUID,
    start: datetime,
    end: datetime,
    *,
    cutoff: datetime | None = None,
) -> Metrics:
    cutoff = cutoff or end
    effective_end = _effective_end(start, end, cutoff)

    transactions = list(
        db.scalars(
            select(Transaction).where(
                Transaction.business_id == business_id,
                Transaction.status == "POSTED",
                Transaction.occurred_at >= start,
                Transaction.occurred_at < effective_end,
            )
        )
    )

    original_ids = {tx.reversal_of for tx in transactions if tx.reversal_of}
    originals: dict[uuid.UUID, Transaction] = {}
    if original_ids:
        originals = {
            tx.id: tx
            for tx in db.scalars(select(Transaction).where(Transaction.id.in_(original_ids)))
        }

    sales = payments = withdrawals = contributions = ZERO
    digital_sales = cash_sales = ZERO

    for tx in transactions:
        kind = tx.kind
        sign = Decimal("1")
        medium = tx.medium
        if kind == ledger_domain.REVERSAL:
            original = originals.get(tx.reversal_of) if tx.reversal_of else None
            if original is None or original.kind not in ledger_domain.METRIC_BY_KIND:
                continue
            kind = original.kind
            medium = original.medium
            sign = Decimal("-1")
        elif kind not in ledger_domain.METRIC_BY_KIND:
            # OPENING_BALANCE, UNKNOWN_OUTFLOW y CLASSIFICATION_ADJUSTMENT no
            # son ventas, gastos ni retiros independientes.
            continue

        value = sign * tx.amount
        if kind == ledger_domain.SALE:
            sales += value
            if medium == ledger_domain.CASH:
                cash_sales += value
            else:
                digital_sales += value
        elif kind == ledger_domain.BUSINESS_PAYMENT:
            payments += value
        elif kind == ledger_domain.HOUSEHOLD_WITHDRAWAL:
            withdrawals += value
        elif kind == ledger_domain.OWNER_CONTRIBUTION:
            contributions += value

    pending = db.scalar(
        select(func.count())
        .select_from(ClassificationRequest)
        .join(Transaction, Transaction.id == ClassificationRequest.transaction_id)
        .where(
            ClassificationRequest.business_id == business_id,
            ClassificationRequest.status == "OPEN",
            Transaction.occurred_at >= start,
            Transaction.occurred_at < effective_end,
        )
    )

    balance_rows = db.execute(
        select(Account.kind, func.coalesce(func.sum(LedgerEntry.delta), 0))
        .join(Account, Account.id == LedgerEntry.account_id)
        .join(Transaction, Transaction.id == LedgerEntry.transaction_id)
        .where(
            Account.business_id == business_id,
            Transaction.status == "POSTED",
            Transaction.occurred_at < effective_end,
        )
        .group_by(Account.kind)
    ).all()
    raw_balances = {
        kind: Decimal(str(total or 0)).quantize(Decimal("0.01")) for kind, total in balance_rows
    }

    capture_errors = db.scalar(
        select(func.count())
        .select_from(InboundEvent)
        .where(
            InboundEvent.business_id == business_id,
            InboundEvent.provider == "simulator",
            InboundEvent.status.in_(["PENDING", "PROCESSING", "RETRY", "DEAD"]),
            InboundEvent.received_at >= start,
            InboundEvent.received_at < effective_end,
        )
    )
    if capture_errors:
        coverage = "CAPTURE_ERRORS"
    elif not transactions:
        coverage = "NO_DATA"
    elif pending:
        coverage = "PARTIAL_CLASSIFICATION"
    else:
        coverage = "RECORDED_ONLY"

    return Metrics(
        sales=sales.quantize(Decimal("0.01")),
        digital_sales=digital_sales.quantize(Decimal("0.01")),
        cash_sales=cash_sales.quantize(Decimal("0.01")),
        payments=payments.quantize(Decimal("0.01")),
        withdrawals=withdrawals.quantize(Decimal("0.01")),
        contributions=contributions.quantize(Decimal("0.01")),
        business_digital_balance=raw_balances.get(ledger_domain.BUSINESS_DIGITAL, ZERO),
        household_digital_balance=raw_balances.get(ledger_domain.HOUSEHOLD_DIGITAL, ZERO),
        declared_cash_balance=raw_balances.get(ledger_domain.CASH_DECLARED, ZERO),
        pending_classifications=int(pending or 0),
        coverage_status=coverage,
    )


# ---------------------------------------------------------------------------
# Hechos semanales
# ---------------------------------------------------------------------------


def latest_fact(db: Session, business_id: uuid.UUID, week: datetime) -> WeeklyFact | None:
    return db.scalar(
        select(WeeklyFact)
        .where(WeeklyFact.business_id == business_id, WeeklyFact.week_start == week)
        .order_by(WeeklyFact.revision.desc())
    )


def _week_sales(db: Session, business_id: uuid.UUID, week: datetime) -> Decimal:
    fact = latest_fact(db, business_id, week)
    if fact is not None:
        return fact.sales
    return compute_metrics(db, business_id, week, week + WEEK, cutoff=week + WEEK).sales


def _week_flow(db: Session, business_id: uuid.UUID, week: datetime) -> Decimal:
    fact = latest_fact(db, business_id, week)
    if fact is not None:
        return fact.operating_flow
    return compute_metrics(db, business_id, week, week + WEEK, cutoff=week + WEEK).operating_flow


def count_stable_weeks(db: Session, business_id: uuid.UUID, anchor: datetime) -> int:
    """Semanas consecutivas estables inmediatamente anteriores a ``anchor``."""
    count = 0
    for index in range(1, settings.stability_weeks + 1):
        week = anchor - timedelta(weeks=index)
        fact = latest_fact(db, business_id, week)
        if fact is not None and fact.stable and fact.week_start + WEEK <= utcnow():
            count += 1
        else:
            break
    return count


def last_flows(
    db: Session, business_id: uuid.UUID, anchor: datetime, weeks: int = 8
) -> list[Decimal]:
    return [
        _week_flow(db, business_id, anchor - timedelta(weeks=index))
        for index in range(1, weeks + 1)
    ]


def previous_four_sales(db: Session, business_id: uuid.UUID, start: datetime) -> list[Decimal]:
    facts = [latest_fact(db, business_id, start - timedelta(weeks=index)) for index in range(1, 5)]
    if any(fact is None or fact.coverage_status != "RECORDED_ONLY" for fact in facts):
        return []
    values = [_week_sales(db, business_id, start - timedelta(weeks=index)) for index in range(1, 5)]
    if any(value <= 0 for value in values):
        return []
    return values


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------


def resolve_period(cutoff: datetime, kind: str | None = None) -> tuple[datetime, datetime, str]:
    """Determina el periodo del reporte.

    - ``PRELIMINARY``: semana en curso hasta el corte.
    - ``WEEKLY_FINAL``: última semana completa anterior al inicio de la semana
      del corte (por ejemplo, el lunes 00:05 se consolida la semana terminada).
    - ``AUTO``: consolida la semana anterior si el corte cae en las primeras
      horas del lunes; en cualquier otro momento genera un preliminar.
    """
    current_start = week_start(cutoff)
    if kind == "WEEKLY_FINAL":
        return current_start - WEEK, current_start, "WEEKLY_FINAL"
    if kind == "PRELIMINARY":
        return current_start, current_start + WEEK, "PRELIMINARY"
    if cutoff - current_start <= timedelta(hours=12):
        return current_start - WEEK, current_start, "WEEKLY_FINAL"
    return current_start, current_start + WEEK, "PRELIMINARY"


def _next_revision(db: Session, business_id: uuid.UUID, period_start: datetime, kind: str) -> int:
    current = db.scalar(
        select(func.max(WeeklyReport.revision)).where(
            WeeklyReport.business_id == business_id,
            WeeklyReport.period_start == period_start,
            WeeklyReport.kind == kind,
        )
    )
    return int(current or 0) + 1


def _comparison_text(
    db: Session,
    business_id: uuid.UUID,
    start: datetime,
    end: datetime,
    kind: str,
    cutoff: datetime,
    current_sales: Decimal,
) -> str:
    previous_start = start - WEEK
    previous_metrics = compute_metrics(db, business_id, previous_start, start, cutoff=start)
    if (
        previous_metrics.coverage_status != "RECORDED_ONLY"
        or previous_metrics.pending_classifications
    ):
        return "sin base suficiente para comparar"
    if kind == "WEEKLY_FINAL":
        previous = _week_sales(db, business_id, previous_start)
    else:
        # Mismo tramo de la semana previa al corte del preliminar.
        elapsed = min(end, cutoff) - start
        previous = compute_metrics(
            db,
            business_id,
            previous_start,
            previous_start + elapsed,
            cutoff=previous_start + elapsed,
        ).sales
    return comparison_label(current_sales, previous)


def _evaluate_alerts(
    db: Session,
    business: Business,
    metrics: Metrics,
    kind: str,
    start: datetime,
    cutoff: datetime,
) -> list[AlertData]:
    previous_sales = previous_four_sales(db, business.id, start) if kind == "WEEKLY_FINAL" else []
    shortfall = commitments_service.upcoming_shortfall(db, business.id, now=cutoff)
    details = commitments_service.shortfall_details(db, business.id, now=cutoff)
    return evaluate_alerts(
        AlertInput(
            sales=metrics.sales,
            operating_flow=metrics.operating_flow,
            withdrawals=metrics.withdrawals,
            pending_classifications=metrics.pending_classifications,
            previous_sales=previous_sales,
            capture_failures=metrics.coverage_status == "CAPTURE_ERRORS",
            shortfall_by_medium=shortfall,
            shortfall_details=details,
            sales_drop_threshold=Decimal(str(settings.sales_drop_threshold)),
        )
    )


def generate_report(
    db: Session,
    business: Business,
    *,
    cutoff_at: datetime | None = None,
    kind: str | None = None,
    actor_id: uuid.UUID | None = None,
    commit: bool = True,
    period_start: datetime | None = None,
    force_revision: bool = False,
) -> WeeklyReport:
    _lock_display_accounts(db, business.id)
    cutoff = cutoff_at or utcnow()
    start, end, kind = resolve_period(cutoff, kind)
    if period_start is not None:
        start, end = period_start, period_start + WEEK

    existing = db.scalar(
        select(WeeklyReport).where(
            WeeklyReport.business_id == business.id,
            WeeklyReport.period_start == start,
            WeeklyReport.kind == kind,
            WeeklyReport.data_cutoff_at == cutoff,
        )
    )
    if existing is not None and not force_revision:
        return existing

    metrics = compute_metrics(db, business.id, start, end, cutoff=cutoff)
    coverage = coverage_dict(metrics)
    alert_data = _evaluate_alerts(db, business, metrics, kind, start, cutoff)
    advice_code = choose_advice(
        [alert.code for alert in alert_data],
        metrics.pending_classifications,
        metrics.sales,
    )
    comparison_text = (
        _comparison_text(db, business.id, start, end, kind, cutoff, metrics.sales)
        if metrics.coverage_status == "RECORDED_ONLY"
        else "sin base suficiente para comparar"
    )
    text = render_report(metrics, alert_data, advice_code, comparison_text=comparison_text)

    report = WeeklyReport(
        business_id=business.id,
        period_start=start,
        period_end=end,
        data_cutoff_at=cutoff,
        kind=kind,
        revision=_next_revision(db, business.id, start, kind),
        metrics_json=metrics.to_public_dict(),
        coverage_json=coverage,
        advice_code=advice_code,
        text=text,
        rules_version=settings.rules_version,
        generated_at=utcnow(),
    )
    db.add(report)
    db.flush()

    alerts_service.persist_for_report(db, business.id, report.id, alert_data)

    if kind == "WEEKLY_FINAL":
        _persist_fact(db, business, report, metrics, alert_data, cutoff)
    anchor = end if kind == "WEEKLY_FINAL" else start
    preferences = db.get(Preference, business.id)
    opportunity_input = OpportunityInput(
        stable_weeks=count_stable_weeks(db, business.id, anchor),
        required_weeks=settings.stability_weeks,
        active_alerts=bool(alert_data),
        invitations_consent=(preferences is None or preferences.invitations_enabled)
        and consents_service.has_active(db, business.id, "PRODUCT_INVITATIONS"),
        coverage_ok=(
            metrics.coverage_status == "RECORDED_ONLY" and metrics.pending_classifications == 0
        ),
        debt_status=business.demo_debt_status,
        credit_active=business.demo_credit_active,
        last_flows=last_flows(db, business.id, anchor, settings.stability_weeks),
        installment_ratio=Decimal(str(settings.demo_weekly_installment_ratio)),
    )
    opportunities_service.persist(db, business, report, evaluate(opportunity_input))

    if commit:
        db.commit()
        db.refresh(report)
    return report


def _persist_fact(
    db: Session,
    business: Business,
    report: WeeklyReport,
    metrics: Metrics,
    alert_data: list[AlertData],
    cutoff: datetime,
) -> WeeklyFact | None:
    latest = latest_fact(db, business.id, report.period_start)
    if latest is not None and latest.data_cutoff_at == cutoff:
        return latest

    stable = (
        metrics.coverage_status == "RECORDED_ONLY"
        and metrics.sales > 0
        and metrics.operating_flow > 0
        and metrics.pending_classifications == 0
        and not alert_data
    )
    fact = WeeklyFact(
        business_id=business.id,
        week_start=report.period_start,
        revision=(latest.revision + 1) if latest is not None else 1,
        sales=metrics.sales,
        payments=metrics.payments,
        withdrawals=metrics.withdrawals,
        contributions=metrics.contributions,
        operating_flow=metrics.operating_flow,
        coverage_status=metrics.coverage_status,
        stable=stable,
        rules_version=settings.rules_version,
        data_cutoff_at=cutoff,
    )
    db.add(fact)
    db.flush()
    return fact


def serialize_report(db: Session, report: WeeklyReport, environment: str = "DEMO") -> dict:
    alerts = alerts_service.list_for_report(db, report.id)
    primary = min(alerts, key=lambda alert: PRIORITY.get(alert.code, 99), default=None)
    opportunity = opportunities_service.get_for_report(db, report.id)
    opportunity_data = opportunities_service.to_public_dict(opportunity)
    prefs = db.get(Preference, report.business_id)
    last_change = db.scalar(
        select(func.max(Transaction.confirmed_at)).where(
            Transaction.business_id == report.business_id
        )
    )
    reason = None
    if not consents_service.has_active(db, report.business_id, "PRODUCT_INVITATIONS"):
        reason = "CONSENT_MISSING"
    elif prefs is not None and not prefs.invitations_enabled:
        reason = "INVITATIONS_DISABLED"
    elif last_change is not None and last_change > report.generated_at:
        reason = "STALE_REPORT"
    if reason and opportunity_data.get("eligible"):
        opportunity_data = {
            **opportunity_data,
            "eligible": False,
            "product_type": None,
            "weekly_installment_cap": None,
            "reasons": [reason],
        }
    metrics = dict(report.metrics_json)
    metrics.setdefault("digital_sales", "0.00")
    metrics.setdefault("cash_sales", "0.00")
    metrics.setdefault("registered_variation", "0.00")
    return {
        "report_id": report.id,
        "environment": environment,
        "kind": report.kind,
        "period_start": report.period_start,
        "period_end": report.period_end,
        "data_cutoff_at": report.data_cutoff_at,
        "revision": report.revision,
        "rules_version": report.rules_version,
        "metrics": metrics,
        "quality": report.coverage_json,
        "primary_alert": primary.code if primary else None,
        "advice_code": report.advice_code,
        "opportunity": opportunity_data,
        "text": report.text,
    }


def latest_report(
    db: Session,
    business_id: uuid.UUID,
    *,
    period_start: datetime | None = None,
) -> WeeklyReport | None:
    stmt = select(WeeklyReport).where(WeeklyReport.business_id == business_id)
    if period_start is not None:
        stmt = stmt.where(WeeklyReport.period_start == period_start)
    stmt = stmt.order_by(
        WeeklyReport.period_start.desc(),
        WeeklyReport.generated_at.desc(),
        WeeklyReport.revision.desc(),
    )
    return db.scalar(stmt)


def revisions(db: Session, business_id: uuid.UUID, period_start: datetime) -> list[int]:
    rows = db.scalars(
        select(WeeklyReport.revision)
        .where(
            WeeklyReport.business_id == business_id,
            WeeklyReport.period_start == period_start,
        )
        .order_by(WeeklyReport.revision.asc())
    )
    return sorted(set(rows))


def comparison_for_report(db: Session, business: Business, report: WeeklyReport) -> str | None:
    metrics = db.scalar(select(WeeklyReport.metrics_json).where(WeeklyReport.id == report.id))
    if not metrics:
        return None
    current = Decimal(str(metrics.get("sales_collected", "0.00")))
    return _comparison_text(
        db,
        business.id,
        report.period_start,
        report.period_end,
        report.kind,
        report.data_cutoff_at,
        current,
    )


def opportunity_display_flow_cap(flows: list[Decimal]) -> str | None:
    positive = [value for value in flows if value > 0]
    if not positive or len(positive) != len(flows):
        return None
    return money_str(min(positive) * Decimal(str(settings.demo_weekly_installment_ratio)))


__all__ = [
    "compute_metrics",
    "count_stable_weeks",
    "generate_report",
    "latest_fact",
    "latest_report",
    "revisions",
    "resolve_period",
    "serialize_report",
]
