"""Persistencia de evaluaciones ilustrativas de ahorro/crédito."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.business.models import Business
from app.modules.insights.models import WeeklyReport
from app.modules.opportunities.domain import OpportunityResult
from app.modules.opportunities.models import OpportunityEvaluation

settings = get_settings()


def persist(
    db: Session,
    business: Business,
    report: WeeklyReport,
    result: OpportunityResult,
) -> OpportunityEvaluation:
    existing = db.scalar(
        select(OpportunityEvaluation).where(OpportunityEvaluation.report_id == report.id)
    )
    if existing is not None:
        return existing

    evaluation = OpportunityEvaluation(
        business_id=business.id,
        report_id=report.id,
        eligible=result.eligible,
        product_type=result.product_type,
        reasons_json=result.reasons,
        stable_weeks=result.stable_weeks,
        demo_debt_status=business.demo_debt_status,
        weekly_installment_cap=result.weekly_installment_cap,
        rules_version=settings.rules_version,
        is_simulated=True,
    )
    db.add(evaluation)
    db.flush()
    return evaluation


def get_for_report(db: Session, report_id: uuid.UUID) -> OpportunityEvaluation | None:
    return db.scalar(
        select(OpportunityEvaluation).where(OpportunityEvaluation.report_id == report_id)
    )


def to_public_dict(evaluation: OpportunityEvaluation | None) -> dict:
    if evaluation is None:
        return {"eligible": False, "reasons": ["NOT_EVALUATED"], "simulated": True}
    return {
        "eligible": evaluation.eligible,
        "product_type": evaluation.product_type,
        "reasons": evaluation.reasons_json,
        "stable_weeks": evaluation.stable_weeks,
        "weekly_installment_cap": (
            f"{evaluation.weekly_installment_cap:.2f}"
            if evaluation.weekly_installment_cap is not None
            else None
        ),
        "simulated": True,
    }
