"""Rutas de clasificación de movimientos ambiguos."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.db.session import get_db
from app.modules.classification import service as classification_service
from app.modules.classification.schemas import ResolutionRequest, ResolutionResponse
from app.modules.ledger import service as ledger_service

router = APIRouter(tags=["classification"])


@router.get("/classifications")
def list_classifications(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = classification_service.list_open(db, ctx.business.id)
    return [
        {
            "id": str(row.id),
            "transaction_id": str(row.transaction_id),
            "status": row.status,
            "options": row.options,
            "version": row.version,
            "expires_at": row.expires_at.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/classifications/{request_id}/resolution",
    response_model=ResolutionResponse,
)
def resolve_classification(
    request_id: uuid.UUID,
    payload: ResolutionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        request, transaction = classification_service.resolve(
            db,
            business_id=business.id,
            request_id=request_id,
            option=payload.option,
            expected_version=payload.expected_version,
            actor_id=ctx.user.id,
            commit=False,
        )
        body = {
            "transaction": ledger_service.transaction_to_dict(transaction),
            "status": request.status,
            "version": request.version,
            "message": "Clasificación actualizada sin duplicar el importe.",
        }
        return 200, body

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route=f"POST /classifications/{request_id}/resolution",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)
