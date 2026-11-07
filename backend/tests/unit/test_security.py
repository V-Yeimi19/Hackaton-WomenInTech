"""Pruebas de normalización, cifrado y firma del simulador."""

from __future__ import annotations

import time

from app.core.security import (
    decrypt_phone,
    encrypt_phone,
    normalize_phone,
    phone_lookup_hash,
    sign_simulator_payload,
    verify_simulator_signature,
)


def test_normaliza_telefono_peruano() -> None:
    assert normalize_phone("999999999") == "+51999999999"
    assert normalize_phone("+51 999 999 999") == "+51999999999"
    assert normalize_phone("0051999999999") == "+51999999999"


def test_hash_de_telefono_es_deterministico() -> None:
    assert phone_lookup_hash("999999999") == phone_lookup_hash("+51999999999")


def test_cifrado_de_telefono_ida_y_vuelta() -> None:
    encrypted = encrypt_phone("+51999999999")
    assert encrypted != "+51999999999"
    assert decrypt_phone(encrypted) == "+51999999999"


def test_firma_del_simulador_valida_y_rechaza_manipulacion() -> None:
    timestamp = str(int(time.time()))
    body = b'{"event_id":"demo-event-1"}'
    signature = sign_simulator_payload(timestamp, body)
    assert verify_simulator_signature(timestamp, body, signature) is True
    assert verify_simulator_signature(timestamp, body + b" ", signature) is False
    assert verify_simulator_signature("1", body, signature) is False
