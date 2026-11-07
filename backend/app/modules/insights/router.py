"""Rutas de reportes semanales, alertas y oportunidades."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.core.rate_limit import enforce
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.alerts import service as alerts_service
from app.modules.insights import service as insights_service
from app.modules.insights.schemas import (
    ReportListResponse,
    ReportOut,
    ReportPreviewRequest,
    ReportResponse,
)

router = APIRouter(tags=["insights"])


def _report_out(data: dict) -> ReportOut:
    return ReportOut(**data)


@router.get("/reports", response_model=ReportListResponse)
def get_report(
    period_start: datetime | None = None,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> ReportListResponse:
    report = insights_service.latest_report(db, ctx.business.id, period_start=period_start)
    if report is None:
        return ReportListResponse(
            report=None,
            revisions=[],
            message="Aún no hay un reporte para este periodo. Solicita una vista previa.",
        )
    data = insights_service.serialize_report(db, report, ctx.business.environment)
    return ReportListResponse(
        report=_report_out(data),
        revisions=insights_service.revisions(db, ctx.business.id, report.period_start),
    )


@router.post("/reports/preview", response_model=ReportResponse)
def preview_report(
    payload: ReportPreviewRequest | None = None,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> ReportResponse:
    enforce(db, str(ctx.session.id), "report-preview", 30)
    now = utcnow()
    cutoff = payload.cutoff_at if payload and payload.cutoff_at else now
    if cutoff > now:
        cutoff = now
    kind = payload.kind if payload else "AUTO"
    report = insights_service.generate_report(
        db,
        ctx.business,
        cutoff_at=cutoff,
        kind=None if kind == "AUTO" else kind,
        actor_id=ctx.user.id,
    )
    data = insights_service.serialize_report(db, report, ctx.business.environment)
    return ReportResponse(
        report=_report_out(data),
        revisions=insights_service.revisions(db, ctx.business.id, report.period_start),
    )


@router.get("/alerts")
def list_alerts(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> list[dict]:
    report = insights_service.latest_report(db, ctx.business.id)
    if report is None:
        return []
    rows = alerts_service.list_for_report(db, report.id)
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "severity": row.severity,
            "evidence": row.evidence_json,
            "status": row.status,
            "report_id": str(row.report_id),
        }
        for row in rows
    ]


@router.get("/opportunities/latest")
def latest_opportunity(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> dict:
    report = insights_service.latest_report(db, ctx.business.id)
    if report is None:
        return {
            "eligible": False,
            "reasons": ["NO_REPORT"],
            "simulated": True,
        }
    data = insights_service.serialize_report(db, report)["opportunity"]
    data["report_id"] = str(report.id)
    return data
