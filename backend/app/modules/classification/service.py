"""Resolución de movimientos ambiguos.

Un movimiento ambiguo ya afectó el saldo del bolsillo negocio (RN-11). Resolverlo
no crea un segundo movimiento de dinero: solo cambia su categoría final.

- ``BUSINESS_PAYMENT``: se reclasifica la operación original (sin asientos nuevos).
- ``HOUSEHOLD_WITHDRAWAL``: se publica un ajuste balanceado que mueve la
  contrapartida externa a ``HOUSEHOLD_DIGITAL`` y se reclasifica el original.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.audit.service import record as audit_record
from app.modules.classification.models import ClassificationRequest
from app.modules.ledger import domain as ledger_domain
from app.modules.ledger import service as ledger_service
from app.modules.ledger.models import Transaction

settings = get_settings()

OPTIONS = [
    {
        "option": 1,
        "code": "BUSINESS_PAYMENT",
        "label": "Pago del negocio (proveedor, insumos, servicio)",
    },
    {
        "option": 2,
        "code": "HOUSEHOLD_WITHDRAWAL",
        "label": "Dinero que pasé a mi casa",
    },
]


def create_request(
    db: Session,
    business_id: uuid.UUID,
    transaction: Transaction,
    *,
    ttl_hours: int = 72,
) -> ClassificationRequest:
    existing = db.scalar(
        select(ClassificationRequest).where(ClassificationRequest.transaction_id == transaction.id)
    )
    if existing is not None:
        return existing

    request = ClassificationRequest(
        business_id=business_id,
        transaction_id=transaction.id,
        status="OPEN",
        options=OPTIONS,
        version=1,
        expires_at=utcnow() + timedelta(hours=ttl_hours),
    )
    db.add(request)
    db.flush()
    audit_record(
        db,
        business_id,
        "CLASSIFICATION_REQUESTED",
        "classification_request",
        request.id,
        metadata={"transaction_id": str(transaction.id)},
    )
    return request


def get_request(
    db: Session, business_id: uuid.UUID, request_id: uuid.UUID
) -> ClassificationRequest:
    request = db.get(ClassificationRequest, request_id)
    if request is None or request.business_id != business_id:
        raise AppError("NOT_FOUND", "Clasificación no encontrada.", 404)
    return request


def list_open(db: Session, business_id: uuid.UUID) -> list[ClassificationRequest]:
    return list(
        db.scalars(
            select(ClassificationRequest)
            .where(
                ClassificationRequest.business_id == business_id,
                ClassificationRequest.status == "OPEN",
            )
            .order_by(ClassificationRequest.created_at.asc())
        )
    )


def open_for_business(db: Session, business_id: uuid.UUID) -> ClassificationRequest | None:
    return db.scalar(
        select(ClassificationRequest)
        .where(
            ClassificationRequest.business_id == business_id,
            ClassificationRequest.status == "OPEN",
        )
        .order_by(ClassificationRequest.created_at.asc())
    )


def resolve(
    db: Session,
    *,
    business_id: uuid.UUID,
    request_id: uuid.UUID,
    option: str,
    expected_version: int,
    actor_id: uuid.UUID | None = None,
    commit: bool = True,
) -> tuple[ClassificationRequest, Transaction]:
    request = db.scalar(
        select(ClassificationRequest)
        .where(
            ClassificationRequest.id == request_id,
            ClassificationRequest.business_id == business_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if request is None:
        raise AppError("NOT_FOUND", "Clasificación no encontrada.", 404)

    if request.status != "OPEN":
        raise AppError("CLASSIFICATION_ALREADY_RESOLVED", "La clasificación ya fue resuelta.", 409)
    if request.expires_at <= utcnow():
        request.status = "EXPIRED"
        db.commit()
        raise AppError("CLASSIFICATION_EXPIRED", "La consulta expiró. Solicita una nueva.", 409)  # noqa: E501
    if request.version != expected_version:
        raise AppError(
            "CLASSIFICATION_VERSION_CONFLICT",
            "La clasificación cambió desde que la consultaste.",
            409,
            {"current_version": request.version},
        )
    if option not in ("BUSINESS_PAYMENT", "HOUSEHOLD_WITHDRAWAL"):
        raise AppError("INVALID_OPTION", "Opción de clasificación inválida.", 422)

    transaction = db.get(Transaction, request.transaction_id)
    if transaction is None or transaction.business_id != business_id:
        raise AppError("NOT_FOUND", "Movimiento no encontrado.", 404)
    if transaction.kind != ledger_domain.UNKNOWN_OUTFLOW:
        raise AppError(
            "CLASSIFICATION_NOT_APPLICABLE",
            "El movimiento ya no está pendiente de clasificación.",
            409,
        )

    if option == "HOUSEHOLD_WITHDRAWAL":
        ledger_service.post_adjustment(
            db,
            transaction,
            target_account_kind=ledger_domain.HOUSEHOLD_DIGITAL,
            actor_id=actor_id,
            commit=False,
        )

    # La categoría final vive en la operación original; el ajuste no se cuenta
    # como un gasto o retiro adicional.
    transaction.kind = option
    transaction.classification_source = ledger_domain.USER_CONFIRMED

    request.status = "RESOLVED"
    request.resolution = option
    request.resolved_at = utcnow()
    request.resolved_by = actor_id
    request.version += 1

    audit_record(
        db,
        business_id,
        "CLASSIFICATION_RESOLVED",
        "classification_request",
        request.id,
        actor_id=actor_id,
        metadata={
            "transaction_id": str(transaction.id),
            "option": option,
        },
    )
    if commit:
        db.commit()
        db.refresh(request)
        db.refresh(transaction)
    else:
        db.flush()
    return request, transaction
