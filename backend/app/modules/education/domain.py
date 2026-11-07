"""Catálogo determinístico de consejos y contenido educativo (P0)."""

from __future__ import annotations

from app.modules.alerts.domain import EXCESS_WITHDRAWAL, PAYMENT_SHORTFALL, SALES_DROP

ADVICE = {
    "PLAN_NEXT_SUPPLIER_PAYMENT": {
        "title": "Planifica tu próximo pago a proveedor",
        "body": (
            "Revisa cuánto necesitas para tu próximo compromiso y separa ese dinero "
            "antes de pasarlo a casa."
        ),
    },
    "KEEP_HOUSEHOLD_SEPARATE": {
        "title": "Separa casa y negocio",
        "body": (
            "Un retiro es dinero que sale del negocio hacia tu casa; no es un gasto "
            "del negocio. Anotarlo aparte te ayuda a decidir."
        ),
    },
    "REVIEW_SALES_CAPTURE": {
        "title": "Revisa tus cobros registrados",
        "body": (
            "Tus cobros registrados bajaron frente a tu promedio. Revisa si falta "
            "registrar ventas en efectivo o cobros por el QR del negocio."
        ),
    },
    "RESOLVE_PENDING_CLASSIFICATION": {
        "title": "Aclara un movimiento pendiente",
        "body": (
            "Tienes un movimiento sin clasificar. Indicar si fue pago a proveedor o "
            "retiro a casa mejora la lectura de tu semana."
        ),
    },
    "RECORD_SALES": {
        "title": "Registra tus ventas",
        "body": "Registra al menos una venta o cobro para empezar a ver tu semana.",
    },
    "KEEP_RECORDING": {
        "title": "Sigue registrando",
        "body": (
            "Cada cobro y pago registrado mejora tu resumen. Recuerda que el flujo "
            "registrado no equivale a la utilidad exacta del negocio."
        ),
    },
}


def choose_advice(
    alert_codes: list[str],
    pending_classifications: int,
    sales,
) -> str:
    if PAYMENT_SHORTFALL in alert_codes:
        return "PLAN_NEXT_SUPPLIER_PAYMENT"
    if EXCESS_WITHDRAWAL in alert_codes:
        return "KEEP_HOUSEHOLD_SEPARATE"
    if SALES_DROP in alert_codes:
        return "REVIEW_SALES_CAPTURE"
    if pending_classifications > 0:
        return "RESOLVE_PENDING_CLASSIFICATION"
    if sales is not None and sales <= 0:
        return "RECORD_SALES"
    return "KEEP_RECORDING"


def recommend(advice_code: str) -> dict:
    return {"code": advice_code, **ADVICE.get(advice_code, ADVICE["KEEP_RECORDING"])}
