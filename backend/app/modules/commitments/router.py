"""Rutas de compromisos de pago próximos."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.db.session import get_db
from app.modules.commitments import service as commitments_service
from app.modules.commitments.models import Commitment
from app.modules.commitments.schemas import (
    CommitmentCreate,
    CommitmentListResponse,
    CommitmentOut,
)

router = APIRouter(tags=["commitments"])


def _out(commitment: Commitment) -> CommitmentOut:
    return CommitmentOut(
        id=commitment.id,
        label=commitment.label,
        amount=f"{commitment.amount:.2f}",
        due_at=commitment.due_at,
        source=commitment.source,
        status=commitment.status,
        payment_account_id=commitment.payment_account_id,
        paid_transaction_id=commitment.paid_transaction_id,
    )


@router.post("/commitments", response_model=CommitmentOut, status_code=201)
def create_commitment(
    payload: CommitmentCreate,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> CommitmentOut:
    commitment = commitments_service.create(db, ctx.business.id, payload)
    return _out(commitment)


@router.get("/commitments", response_model=CommitmentListResponse)
def list_commitments(
    status: str | None = None,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> CommitmentListResponse:
    rows = commitments_service.list_commitments(db, ctx.business.id, status=status)
    return CommitmentListResponse(items=[_out(row) for row in rows])
