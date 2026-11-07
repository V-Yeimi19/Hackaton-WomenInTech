"""Utilidades de seguridad: tokens, CSRF, cifrado de teléfono y firmas."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()


def hash_token(token: str) -> str:
    """Hash determinístico para almacenar tokens de sesión (nunca en claro)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def _fernet() -> Fernet:
    key = hashlib.sha256(settings.phone_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_phone(phone: str) -> str:
    return _fernet().encrypt(phone.encode("utf-8")).decode("utf-8")


def decrypt_phone(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - configuración inválida
        raise ValueError("No se pudo descifrar el teléfono") from exc


def normalize_phone(raw: str) -> str:
    """Normaliza a E.164 de forma simple para la demo (Perú por defecto)."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not digits:
        raise ValueError("Teléfono vacío")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "51" + digits
    return "+" + digits


def phone_lookup_hash(phone: str) -> str:
    normalized = normalize_phone(phone)
    return hmac.new(
        settings.phone_lookup_key.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _simulator_signature(timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + raw_body
    return hmac.new(
        settings.simulator_signing_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def sign_simulator_payload(timestamp: str, raw_body: bytes) -> str:
    """Helper para el simulador/scripts de demo."""
    return _simulator_signature(timestamp, raw_body)


def verify_simulator_signature(
    timestamp: str,
    raw_body: bytes,
    signature: str,
    tolerance_seconds: int = 300,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > tolerance_seconds:
        return False
    expected = _simulator_signature(timestamp, raw_body)
    return hmac.compare_digest(expected, signature)


def verify_twilio_signature(url: str, params: dict[str, str], signature: str) -> bool:
    """Valida la firma de Twilio. En modo fake no se exige."""
    if settings.messaging_mode != "twilio":
        return True
    if not settings.twilio_auth_token:
        return False
    from twilio.request_validator import RequestValidator  # import diferido

    validator = RequestValidator(settings.twilio_auth_token)
    return bool(validator.validate(url, params, signature))
