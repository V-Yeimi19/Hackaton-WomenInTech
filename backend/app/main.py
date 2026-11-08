"""Punto de entrada FastAPI de Mica · Mi Negocio (P0)."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.errors import AppError, error_payload
from app.modules.agent.router import router as agent_router
from app.modules.audit.router import router as usage_router
from app.modules.business.router import router as business_router
from app.modules.classification.router import router as classification_router
from app.modules.commitments.router import router as commitments_router
from app.modules.consents.router import router as consents_router
from app.modules.demo.router import router as demo_router
from app.modules.education.router import router as education_router
from app.modules.health.router import router as health_router
from app.modules.identity.router import router as identity_router
from app.modules.insights.router import router as insights_router
from app.modules.ledger.router import router as ledger_router
from app.modules.messaging.router import router as webhooks_router
from app.modules.wallets.router import router as wallets_router

settings = get_settings()
logger = logging.getLogger("mica.api")
VERSION = "0.1.0"


def _correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mica.startup environment=%s", settings.app_env)
    yield
    logger.info("mica.shutdown")


def create_app() -> FastAPI:
    docs_enabled = settings.openapi_docs_enabled
    app = FastAPI(
        title="Mica · Mi Negocio API",
        version=VERSION,
        description=(
            "Backend P0 del monoproducto Mi Negocio: libro financiero, "
            "reportes semanales, alertas, oportunidades simuladas y "
            "mensajería WhatsApp en modo fake/Twilio."
        ),
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-CSRF-Token",
            "X-Correlation-ID",
            "X-Mica-Timestamp",
            "X-Mica-Signature",
            "X-Twilio-Signature",
        ],
        expose_headers=["X-Correlation-ID"],
    )

    @app.middleware("http")
    async def correlation_and_headers(request: Request, call_next):
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or uuid.uuid4().hex
        )
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        logger.info(
            "http route=%s status=%s duration_ms=%.2f correlation_id=%s",
            getattr(route, "path", "unmatched"),
            response.status_code,
            (time.perf_counter() - started) * 1000,
            correlation_id,
        )
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                exc.code,
                exc.message,
                _correlation_id(request),
                exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "VALIDATION_ERROR",
                "La solicitud no cumple el contrato.",
                _correlation_id(request),
                jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                "HTTP_ERROR" if exc.status_code >= 500 else "NOT_FOUND",
                str(exc.detail) if exc.detail else "Error HTTP.",
                _correlation_id(request),
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError):
        logger.error(
            "database_error type=%s correlation_id=%s", type(exc).__name__, _correlation_id(request)
        )
        return JSONResponse(
            status_code=503,
            content=error_payload(
                "DATABASE_UNAVAILABLE",
                "La base de datos no está disponible. Reintenta.",
                _correlation_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.error(
            "unhandled_error type=%s correlation_id=%s",
            type(exc).__name__,
            _correlation_id(request),
        )
        return JSONResponse(
            status_code=500,
            content=error_payload(
                "INTERNAL_ERROR",
                "Ocurrió un error inesperado.",
                _correlation_id(request),
            ),
        )

    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(health_router)
    app.include_router(usage_router, prefix="/api/v1")
    app.include_router(education_router, prefix="/api/v1")

    api_prefix = "/api/v1"
    app.include_router(identity_router, prefix=api_prefix)
    app.include_router(business_router, prefix=api_prefix)
    app.include_router(ledger_router, prefix=api_prefix)
    app.include_router(wallets_router, prefix=api_prefix)
    app.include_router(classification_router, prefix=api_prefix)
    app.include_router(commitments_router, prefix=api_prefix)
    app.include_router(insights_router, prefix=api_prefix)
    app.include_router(consents_router, prefix=api_prefix)
    app.include_router(webhooks_router, prefix=api_prefix)
    if settings.app_env == "demo":
        app.include_router(demo_router, prefix=api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "service": "mica-api",
            "version": VERSION,
            "environment": settings.app_env,
            "docs": "/docs" if docs_enabled else None,
            "health": "/health/ready",
        }

    return app


app = create_app()
