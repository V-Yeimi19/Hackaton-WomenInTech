"""Cliente de IA (GroqCloud, API compatible con OpenAI).

Devuelve ``None`` si la IA está apagada o falla: quien llama decide la respuesta
de respaldo. Nunca registra la clave ni el contenido de los mensajes.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("mica.llm")
# httpx registra URLs y cabeceras en INFO; no las queremos en los logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def is_enabled() -> bool:
    return bool(settings.enable_llm and settings.groq_api_key and settings.groq_model)


def chat(messages: list[dict[str, str]], *, max_tokens: int = 900) -> str | None:
    if not is_enabled():
        return None
    body: dict[str, object] = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": 0.4,
        "max_completion_tokens": max_tokens,
    }
    # Los modelos gpt-oss razonan antes de responder; "low" basta para un chat breve.
    if settings.groq_model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    try:
        response = httpx.post(
            f"{settings.groq_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json=body,
            timeout=settings.groq_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"].get("content") or ""
    except httpx.HTTPStatusError as exc:
        logger.warning("llm.failed status=%s", exc.response.status_code)
        return None
    except Exception as exc:  # red, timeout o respuesta inesperada
        logger.warning("llm.failed type=%s", type(exc).__name__)
        return None
    return content.strip() or None
