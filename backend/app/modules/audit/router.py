"""Analítica minimizada: catálogo cerrado, sin texto ni importes del cliente."""

from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.core.rate_limit import enforce
from app.db.session import get_db
from app.modules.audit.service import record

router = APIRouter(tags=["usage"])


class UsageEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["REPORT_OPENED", "BALANCES_OPENED", "EDUCATION_OPENED", "INVITATION_OPENED"]


@router.post("/usage-events", status_code=204)
def usage(
    payload: UsageEvent,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    enforce(db, str(ctx.session.id), "usage-events", 60)
    record(
        db,
        ctx.business.id,
        payload.event,
        "business",
        ctx.business.id,
        actor_id=ctx.user.id,
        metadata={"environment": ctx.business.environment},
    )
    db.commit()
    return Response(status_code=204)
