"""Errores de aplicación y formato uniforme de respuesta.

El contrato HTTP del README exige `code`, `message`, `correlation_id` y detalles
no sensibles. Los handlers se registran en `app.main`.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Error controlado que se traduce a una respuesta HTTP concreta."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_payload(
    code: str,
    message: str,
    correlation_id: str | None = None,
    details: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "correlation_id": correlation_id,
    }
    if details is not None:
        payload["details"] = details
    return payload
