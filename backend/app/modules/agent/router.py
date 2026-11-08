"""Chat de la app e información del negocio compartida con Telegram."""

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.core.deps import BusinessContext, require_business
from app.core.errors import AppError
from app.core.rate_limit import enforce
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.agent import service
from app.modules.agent.models import AgentProfile, AppExchange
from app.modules.messaging import service as messaging
from app.modules.wallets import service as wallets
from app.modules.wallets.models import Wallet

router = APIRouter(tags=["agent"])
Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ProfileUpdate(BaseModel):
    wallet_id: UUID
    answers: list[Answer] = Field(max_length=5)
    expected_version: int = Field(ge=0)


class ProfileResponse(BaseModel):
    wallet_id: UUID
    answers: list[str]
    version: int
    updated_at: datetime | None = None


class ChatRequest(BaseModel):
    wallet_id: UUID
    message: Answer
    request_id: UUID = Field(default_factory=uuid4)


class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request_id: UUID
    message: str
    reply: str
    created_at: datetime


class ChatHistory(BaseModel):
    items: list[ChatResponse]
    next_cursor: UUID | None = None


def business_wallet(
    db: Session, ctx: BusinessContext, wallet_id: UUID, *, lock: bool = False
) -> Wallet:
    wallet = wallets.get_wallet(db, ctx.business.id, wallet_id)
    if not wallets.is_business_wallet(wallet):
        raise AppError("BUSINESS_WALLET_REQUIRED", "Elige una billetera de negocio.", 422)
    if lock:
        wallet = db.scalars(
            select(Wallet)
            .where(
                Wallet.id == wallet.id,
                Wallet.business_id == ctx.business.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
    return wallet


@router.get("/agent/profile", response_model=ProfileResponse)
def profile(
    wallet_id: UUID,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business_wallet(db, ctx, wallet_id)
    record = db.get(AgentProfile, wallet_id)
    return ProfileResponse(
        wallet_id=wallet_id,
        answers=record.answers if record else [],
        version=record.version if record else 0,
        updated_at=record.updated_at if record else None,
    )


@router.patch("/agent/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business_wallet(db, ctx, payload.wallet_id, lock=True)
    record = db.get(AgentProfile, payload.wallet_id, populate_existing=True)
    if payload.expected_version != (record.version if record else 0):
        if record and record.answers == payload.answers:
            return ProfileResponse(
                wallet_id=record.wallet_id,
                answers=record.answers,
                version=record.version,
                updated_at=record.updated_at,
            )
        raise AppError(
            "PROFILE_VERSION_CONFLICT",
            "Tu perfil cambió en otra sesión. Recárgalo antes de guardar.",
            409,
        )
    if record is None:
        record = AgentProfile(
            wallet_id=payload.wallet_id, business_id=ctx.business.id, answers=payload.answers
        )
        db.add(record)
    else:
        record.answers = payload.answers
        record.version += 1
        record.updated_at = utcnow()
    db.commit()
    db.refresh(record)
    return ProfileResponse(
        wallet_id=record.wallet_id,
        answers=record.answers,
        version=record.version,
        updated_at=record.updated_at,
    )


@router.get("/agent/chat", response_model=ChatHistory)
def history(
    wallet_id: UUID,
    limit: int = Query(default=50, ge=1, le=50),
    cursor: UUID | None = None,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business_wallet(db, ctx, wallet_id)
    query = select(AppExchange).where(
        AppExchange.business_id == ctx.business.id, AppExchange.wallet_id == wallet_id
    )
    if cursor:
        previous = db.scalar(query.where(AppExchange.id == cursor))
        if previous is None:
            raise AppError("INVALID_CURSOR", "Página de conversación inválida.", 422)
        query = query.where(
            tuple_(AppExchange.created_at, AppExchange.id) < (previous.created_at, previous.id)
        )
    records = list(
        db.scalars(
            query.order_by(AppExchange.created_at.desc(), AppExchange.id.desc()).limit(limit + 1)
        )
    )
    page = records[:limit]
    return ChatHistory(
        items=[ChatResponse.model_validate(item) for item in reversed(page)],
        next_cursor=page[-1].id if len(records) > limit else None,
    )


@router.post("/agent/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    ctx: BusinessContext = Depends(require_business),
    db: Session = Depends(get_db),
):
    business_wallet(db, ctx, payload.wallet_id)
    enforce(db, str(ctx.business.id), "agent-app-chat", 30)
    wallet = business_wallet(db, ctx, payload.wallet_id, lock=True)
    existing = db.scalar(
        select(AppExchange).where(
            AppExchange.wallet_id == wallet.id,
            AppExchange.business_id == ctx.business.id,
            AppExchange.request_id == payload.request_id,
        )
    )
    if existing:
        if existing.message != payload.message:
            raise AppError(
                "CHAT_REQUEST_CONFLICT", "Este identificador ya se utilizó para otro mensaje.", 409
            )
        return existing
    previous = list(
        db.scalars(
            select(AppExchange)
            .where(
                AppExchange.business_id == ctx.business.id,
                AppExchange.wallet_id == wallet.id,
            )
            .order_by(AppExchange.created_at.desc(), AppExchange.id.desc())
            .limit(service.HISTORY_TURNS)
        )
    )
    turns = [
        turn
        for item in reversed(previous)
        for turn in (
            {"role": "user", "content": item.message},
            {"role": "assistant", "content": item.reply},
        )
    ]
    command, _ = messaging.parse_telegram_text(payload.message)
    option = messaging.option_reply(db, ctx.business, command, "app", utcnow())
    suggestion = messaging.suggest_telegram_option(payload.message)
    reply: str | None
    if option:
        reply = option[0]
    elif suggestion:
        reply = f"¿Quisiste decir {suggestion}? Escribe {suggestion} para elegir esa opción."
    else:
        reply = service.generate_answer(db, ctx.business, payload.message, "la app", turns, wallet)
        if not reply:
            reply = service.offline_wallet_answer(db, wallet, payload.message)
    exchange = AppExchange(
        business_id=ctx.business.id,
        wallet_id=wallet.id,
        request_id=payload.request_id,
        message=payload.message,
        reply=service.clean_reply(reply),
    )
    db.add(exchange)
    db.commit()
    db.refresh(exchange)
    return exchange
