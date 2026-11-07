"""Rutas del libro: pagos, transferencias, efectivo, historial y correcciones."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.core.errors import AppError
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.classification import service as classification_service
from app.modules.commitments import service as commitments_service
from app.modules.ledger import domain as ledger_domain
from app.modules.ledger import service as ledger_service
from app.modules.ledger.models import Transaction
from app.modules.ledger.schemas import (
    CashRecordRequest,
    CashRecordResponse,
    CorrectionRequest,
    CorrectionResponse,
    PaymentRequest,
    PaymentResponse,
    TransactionListResponse,
    TransactionOut,
    TransferRequest,
    TransferResponse,
)
from app.shared.clock import parse_datetime
from app.shared.money import Money, money_str

router = APIRouter(tags=["ledger"])


def _balances(db: Session, business_id: uuid.UUID) -> dict[str, str]:
    return ledger_service.balances(db, business_id)


def _transaction_out(transaction: Transaction) -> TransactionOut:
    return TransactionOut(**ledger_service.transaction_to_dict(transaction))


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    cursor: str | None = None,
    limit: int = 20,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    rows, next_cursor = ledger_service.list_transactions(
        db, ctx.business.id, cursor=cursor, limit=limit
    )
    return TransactionListResponse(
        items=[_transaction_out(row) for row in rows],
        next_cursor=next_cursor,
    )


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    payload: PaymentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        money = Money.parse(payload.amount, payload.currency)
        if payload.ambiguous and payload.commitment_id is not None:
            raise AppError(
                "AMBIGUOUS_WITH_COMMITMENT",
                "Un pago ambiguo no puede vincularse a un compromiso.",
                422,
            )

        commitment = None
        if payload.commitment_id is not None:
            commitment = commitments_service.get(db, business.id, payload.commitment_id)
            account = ledger_service.get_account(db, business.id, ledger_domain.BUSINESS_DIGITAL)
            if commitment.payment_account_id != account.id:
                raise AppError(
                    "COMMITMENT_MEDIUM_MISMATCH", "Este pago requiere un compromiso digital.", 422
                )
            if commitment.status != "OPEN":
                raise AppError("COMMITMENT_NOT_OPEN", "El compromiso ya no está abierto.", 409)
            if commitment.amount != money.amount:
                raise AppError(
                    "COMMITMENT_AMOUNT_MISMATCH",
                    "En P0 el pago debe cubrir el importe completo del compromiso.",
                    422,
                )

        occurred_at = parse_datetime(payload.occurred_at) if payload.occurred_at else utcnow()
        kind = (
            ledger_domain.UNKNOWN_OUTFLOW if payload.ambiguous else ledger_domain.BUSINESS_PAYMENT
        )
        classification_source = (
            ledger_domain.PENDING if payload.ambiguous else ledger_domain.EXPLICIT_ACTION
        )
        transaction = ledger_service.post(
            db,
            business_id=business.id,
            kind=kind,
            amount=money.amount,
            medium=ledger_domain.DIGITAL,
            source=ledger_domain.USER_DECLARED,
            environment=business.environment,
            classification_source=classification_source,
            occurred_at=occurred_at,
            description=payload.description or f"Pago a {payload.provider}",
            actor_id=ctx.user.id,
            commit=False,
        )

        request = None
        if payload.ambiguous:
            request = classification_service.create_request(db, business.id, transaction)

        if commitment is not None:
            commitments_service.mark_paid(db, commitment, transaction.id)

        body = {
            "transaction_id": str(transaction.id),
            "status": transaction.status,
            "environment": transaction.environment,
            "kind": transaction.kind,
            "amount": money_str(transaction.amount),
            "balances": _balances(db, business.id),
            "classification_request_id": str(request.id) if request else None,
            "message": (
                "Pago registrado. Indica si fue pago del negocio o retiro a casa "
                "para completar la lectura de tu semana."
                if payload.ambiguous
                else f"Pagaste S/{money_str(money.amount)} a {payload.provider} en esta demostración."
            ),
        }
        return 201, body

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route="POST /payments",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)


@router.post("/household-transfers", response_model=TransferResponse, status_code=201)
def create_household_transfer(
    payload: TransferRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        money = Money.parse(payload.amount, payload.currency)
        occurred_at = parse_datetime(payload.occurred_at) if payload.occurred_at else utcnow()
        if payload.direction == "BUSINESS_TO_HOME":
            kind = ledger_domain.HOUSEHOLD_WITHDRAWAL
            message = f"Pasaste S/{money_str(money.amount)} a casa en esta demostración."
        else:
            kind = ledger_domain.OWNER_CONTRIBUTION
            message = f"Aportaste S/{money_str(money.amount)} al negocio en esta demostración."

        transaction = ledger_service.post(
            db,
            business_id=business.id,
            kind=kind,
            amount=money.amount,
            medium=ledger_domain.DIGITAL,
            source=ledger_domain.USER_DECLARED,
            environment=business.environment,
            occurred_at=occurred_at,
            description=payload.direction,
            actor_id=ctx.user.id,
            commit=False,
        )
        body = {
            "transaction_id": str(transaction.id),
            "status": transaction.status,
            "environment": transaction.environment,
            "kind": transaction.kind,
            "amount": money_str(transaction.amount),
            "balances": _balances(db, business.id),
            "message": message,
        }
        return 201, body

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route="POST /household-transfers",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)


@router.post("/cash-records", response_model=CashRecordResponse, status_code=201)
def create_cash_record(
    payload: CashRecordRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business

    def execute() -> tuple[int, dict]:
        money = Money.parse(payload.amount, payload.currency)
        occurred_at = parse_datetime(payload.occurred_at) if payload.occurred_at else utcnow()
        kind = ledger_domain.SALE if payload.type == "SALE" else ledger_domain.BUSINESS_PAYMENT
        transaction = ledger_service.post(
            db,
            business_id=business.id,
            kind=kind,
            amount=money.amount,
            medium=ledger_domain.CASH,
            source=ledger_domain.USER_DECLARED,
            environment=business.environment,
            occurred_at=occurred_at,
            description=payload.description or "Registro en efectivo declarado",
            actor_id=ctx.user.id,
            commit=False,
        )
        body = {
            "transaction_id": str(transaction.id),
            "status": transaction.status,
            "environment": transaction.environment,
            "kind": transaction.kind,
            "amount": money_str(transaction.amount),
            "balances": _balances(db, business.id),
            "message": (
                "Venta en efectivo declarada. Solo afecta tu caja física declarada."
                if payload.type == "SALE"
                else "Gasto en efectivo declarado. Solo afecta tu caja física declarada."
            ),
        }
        return 201, body

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route="POST /cash-records",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)


@router.post(
    "/transactions/{transaction_id}/corrections",
    response_model=CorrectionResponse,
)
def correct_transaction(
    transaction_id: uuid.UUID,
    payload: CorrectionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business = ctx.business
    original = db.get(Transaction, transaction_id)
    if original is None or original.business_id != business.id:
        raise AppError("NOT_FOUND", "Movimiento no encontrado.", 404)
    if original.source == ledger_domain.PROVIDER_CONFIRMED:
        raise AppError(
            "CORRECTION_NOT_ALLOWED",
            "Un movimiento confirmado por un proveedor no se corrige por declaración.",
            422,
        )
    if original.kind not in (
        ledger_domain.SALE,
        ledger_domain.BUSINESS_PAYMENT,
        ledger_domain.HOUSEHOLD_WITHDRAWAL,
        ledger_domain.OWNER_CONTRIBUTION,
    ):
        raise AppError(
            "CORRECTION_NOT_ALLOWED",
            "Este movimiento no es corregible. Resuelve su clasificación si corresponde.",
            422,
        )

    def execute() -> tuple[int, dict]:
        existing_reversal = db.scalar(
            select(Transaction).where(Transaction.reversal_of == original.id)
        )
        if existing_reversal is not None:
            raise AppError("ALREADY_REVERSED", "El movimiento ya fue corregido.", 409)
        reversal = ledger_service.post_reversal(
            db,
            original,
            reason=payload.reason,
            actor_id=ctx.user.id,
            commit=False,
        )
        replacement = None
        if payload.replacement is not None:
            money = Money.parse(payload.replacement.amount, payload.replacement.currency)
            occurred_at = (
                parse_datetime(payload.replacement.occurred_at)
                if payload.replacement.occurred_at
                else utcnow()
            )
            replacement = ledger_service.post(
                db,
                business_id=business.id,
                kind=original.kind,
                amount=money.amount,
                medium=payload.replacement.medium,
                source=ledger_domain.USER_DECLARED,
                environment=business.environment,
                classification_source=ledger_domain.USER_CONFIRMED,
                occurred_at=occurred_at,
                description=payload.replacement.description or payload.reason,
                actor_id=ctx.user.id,
                commit=False,
            )
            replacement.replacement_for = original.id
            db.flush()

        body = {
            "original": ledger_service.transaction_to_dict(original),
            "reversal": ledger_service.transaction_to_dict(reversal),
            "replacement": (
                ledger_service.transaction_to_dict(replacement) if replacement else None
            ),
            "message": "Corrección registrada como reversión y reemplazo trazables.",
        }
        return 200, body

    status_code, body = ledger_service.run_idempotent(
        db,
        business_id=business.id,
        route=f"POST /transactions/{transaction_id}/corrections",
        key=idempotency_key,
        payload=payload.model_dump(mode="json"),
        fn=execute,
    )
    return JSONResponse(status_code=status_code, content=body)
