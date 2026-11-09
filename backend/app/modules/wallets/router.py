"""Rutas de billeteras, yapeos, transferencias entre billeteras y movimientos."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import BusinessContext, require_business
from app.core.errors import AppError
from app.db.session import get_db
from app.modules.ledger import service as ledger_service
from app.modules.wallets import service
from app.modules.wallets.schemas import (
    IncomingYapeRequest,
    MovementListResponse,
    MovementOut,
    OperationResponse,
    WalletArchiveResponse,
    WalletCreate,
    WalletListResponse,
    WalletOut,
    WalletTransferRequest,
    YapeoRequest,
)

router = APIRouter(tags=["wallets"])
settings = get_settings()


def _operation_body(db: Session, business_id: uuid.UUID, transaction) -> dict:
    return {
        "movement": service.get_movement(db, business_id, transaction.id),
        "wallets": _wallets_snapshot(db, business_id),
    }


def _wallets_snapshot(db: Session, business_id: uuid.UUID) -> dict:
    wallets = service.active_wallets(db, business_id)
    return service.wallets_snapshot(db, wallets, business_id)


@router.get("/wallets", response_model=WalletListResponse)
def list_wallets(
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    return service.list_wallets(db, ctx.business.id)


@router.post("/wallets", response_model=WalletOut, status_code=201)
def create_wallet(
    payload: WalletCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        wallet = service.create_wallet(
            db,
            business.id,
            name=payload.name,
            purpose=payload.purpose,
            icon=payload.icon,
            color=payload.color,
            actor_id=ctx.user.id,
        )
        return 201, service.wallet_to_dict(wallet, service.ZERO)

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route="POST /wallets",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/wallets/{wallet_id}", response_model=WalletArchiveResponse)
def archive_wallet(
    wallet_id: uuid.UUID,
    move_to_wallet_id: uuid.UUID | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        body = service.archive_wallet(
            db,
            business.id,
            business.environment,
            wallet_id=wallet_id,
            move_to_wallet_id=move_to_wallet_id,
            actor_id=ctx.user.id,
        )
        return 200, body

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route=f"DELETE /wallets/{wallet_id}",
        key=idempotency_key,
        payload={"move_to_wallet_id": str(move_to_wallet_id) if move_to_wallet_id else None},
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)


@router.post("/wallet-transfers", response_model=OperationResponse, status_code=201)
def create_wallet_transfer(
    payload: WalletTransferRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        transaction = service.transfer(
            db,
            business.id,
            business.environment,
            from_wallet_id=payload.from_wallet_id,
            to_wallet_id=payload.to_wallet_id,
            amount=payload.amount,
            note=payload.note,
            actor_id=ctx.user.id,
        )
        return 201, _operation_body(db, business.id, transaction)

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route="POST /wallet-transfers",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)


@router.post("/yapeos", response_model=OperationResponse, status_code=201)
def create_yapeo(
    payload: YapeoRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        transaction = service.yapeo(
            db,
            business.id,
            business.environment,
            from_wallet_id=payload.from_wallet_id,
            amount=payload.amount,
            counterparty_type=payload.counterparty.type,
            counterparty_name=payload.counterparty.name,
            counterparty_phone=payload.counterparty.phone,
            category=payload.category,
            message=payload.message,
            actor_id=ctx.user.id,
        )
        return 201, _operation_body(db, business.id, transaction)

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route="POST /yapeos",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)


@router.get("/movements", response_model=MovementListResponse)
def list_movements(
    wallet_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = 50,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    items, next_cursor = service.list_movements(
        db, ctx.business.id, wallet_id=wallet_id, cursor=cursor, limit=limit
    )
    return {"items": items, "next_cursor": next_cursor}


@router.get("/movements/{movement_id}", response_model=MovementOut)
def get_movement(
    movement_id: uuid.UUID,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    return service.get_movement(db, ctx.business.id, movement_id)


@router.post("/demo/incoming-yapes", response_model=OperationResponse, status_code=201)
def simulate_incoming_yape(
    payload: IncomingYapeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    if settings.app_env != "demo":
        raise AppError("DEMO_DISABLED", "Demo deshabilitada.", 404)
    business = ctx.business

    def execute() -> tuple[int, dict]:
        transaction = service.receive(
            db,
            business.id,
            business.environment,
            to_wallet_id=payload.to_wallet_id,
            amount=payload.amount,
            from_name=payload.from_name,
        )
        return 201, _operation_body(db, business.id, transaction)

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route="POST /demo/incoming-yapes",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)
