"""Contenido local curado; no publica enlaces institucionales sin validar."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.db.session import get_db
from app.modules.education.domain import recommend
from app.modules.insights.service import latest_report

router = APIRouter(tags=["education"])


@router.get("/education/recommendation")
def recommendation(ctx: BusinessContext = Depends(require_business), db: Session = Depends(get_db)):
    report = latest_report(db, ctx.business.id)
    return recommend(report.advice_code if report and report.advice_code else "KEEP_RECORDING")
