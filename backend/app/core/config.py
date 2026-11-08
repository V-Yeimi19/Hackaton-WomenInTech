"""Configuración central de Mica.

Todos los valores se leen de variables de entorno (o de un archivo .env local).
Los valores por defecto son exclusivamente para desarrollo/demo y no deben usarse
en una exposición pública sin cambiarlos.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[3] / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Entorno
    app_env: str = "demo"
    app_timezone: str = "America/Lima"
    log_level: str = "INFO"

    # Persistencia
    database_url: str = "postgresql+psycopg://mica:mica@localhost:5432/mica"

    # Sesión y seguridad
    session_secret: str = "dev-session-secret-change-me"
    session_ttl_hours: int = 24
    csrf_enabled: bool = True
    phone_encryption_key: str = "dev-phone-encryption-key-change-me"
    phone_lookup_key: str = "dev-phone-lookup-key-change-me"
    simulator_signing_secret: str = "dev-simulator-secret-change-me"

    # URLs públicas
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,http://localhost:5500,"
        "http://127.0.0.1:5500,https://mock-tawny-tau.vercel.app"
    )
    # Límites de yapeo validados en el servidor (soles).
    payment_limit_pen: int = 500
    daily_limit_pen: int = 2000

    # Canales de mensajería: se activan por separado. Mientras WhatsApp espera
    # las verificaciones de Meta/Twilio, la demo usa Telegram.
    whatsapp_enabled: bool = False
    telegram_enabled: bool = True

    # Telegram (sin token, los envíos se simulan)
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    # Si se configura, el webhook exige la cabecera X-Telegram-Bot-Api-Secret-Token.
    telegram_webhook_secret: str = ""
    # El worker consulta getUpdates (útil en local, sin URL pública ni webhook).
    telegram_polling: bool = True
    enable_telegram_audio: bool = True
    telegram_audio_max_bytes: int = Field(default=10_000_000, ge=1, le=20_000_000)
    telegram_audio_max_seconds: int = Field(default=180, ge=1, le=180)

    # Twilio / WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+10000000000"
    twilio_webhook_public_url: str = ""
    twilio_status_public_url: str = ""
    messaging_mode: Literal["fake", "twilio"] = "fake"

    # Reglas de demo
    rules_version: str = "demo-1"
    weekly_report_local_time: str = "20:00"
    stability_weeks: int = 8
    sales_drop_threshold: float = 0.30
    demo_weekly_installment_ratio: float = 0.20

    # Opcionales
    enable_llm: bool = False

    # IA del agente con GroqCloud (API compatible con OpenAI). Se activa con
    # ENABLE_LLM=true; apagada, el agente responde con plantillas.
    groq_api_key: str = ""
    groq_model: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: int = 20
    groq_transcription_model: str = "whisper-large-v3-turbo"
    groq_transcription_timeout_seconds: int = Field(default=30, ge=1, le=30)
    enable_tts: bool = False

    # Comportamiento de demo
    process_inbox_inline: bool = False

    # Trabajo durable
    worker_poll_seconds: int = 5
    worker_batch_size: int = 25
    job_lease_seconds: int = 120
    scheduler_interval_seconds: int = 60
    run_scheduler_in_worker: bool = True
    openapi_docs_enabled: bool = True

    @model_validator(mode="after")
    def validate_public_configuration(self) -> "Settings":
        if self.public_base_url.startswith("https://") or self.app_env != "demo":
            for name in (
                "session_secret",
                "phone_encryption_key",
                "phone_lookup_key",
                "simulator_signing_secret",
            ):
                value = getattr(self, name)
                if value.startswith("dev-") or len(value) < 32:
                    raise ValueError(
                        f"Configura {name} con un secreto aleatorio de al menos 32 caracteres"
                    )
        if self.messaging_mode == "twilio" and not (
            self.twilio_account_sid and self.twilio_auth_token
        ):
            raise ValueError("Twilio requiere Account SID y Auth Token")
        if self.enable_llm and not (self.groq_api_key and self.groq_model):
            raise ValueError("ENABLE_LLM=true requiere GROQ_API_KEY y GROQ_MODEL")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
