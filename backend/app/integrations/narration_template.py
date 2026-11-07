"""Narración determinística del reporte (sin LLM).

Todos los números provienen del snapshot y se formatean con `money_str`. El texto
resultante es el mismo que se usa en la app y en WhatsApp.
"""

from __future__ import annotations

from app.modules.alerts.domain import AlertData
from app.modules.education.domain import ADVICE, recommend
from app.modules.insights.domain import Metrics
from app.shared.money import money_str


def render_report(
    metrics: Metrics,
    alerts: list[AlertData],
    advice_code: str,
    *,
    comparison_text: str | None = None,
) -> str:
    lines: list[str] = []
    lines.append("Tu semana en Mi Negocio")
    lines.append(
        "Registraste S/"
        f"{money_str(metrics.sales)} en cobros: S/{money_str(metrics.digital_sales)} digitales "
        f"y S/{money_str(metrics.cash_sales)} en efectivo declarado."
    )
    if metrics.payments > 0:
        lines.append(f"Pagaste S/{money_str(metrics.payments)} al negocio.")
    if metrics.withdrawals > 0:
        lines.append(f"Pasaste S/{money_str(metrics.withdrawals)} a casa.")
    if metrics.contributions > 0:
        lines.append(f"Aportaste S/{money_str(metrics.contributions)} desde casa.")
    lines.append(
        f"De tus cobros quedaron S/{money_str(metrics.operating_flow)} después de esos pagos "
        "del negocio; esto no es tu ganancia exacta."
    )
    lines.append(
        f"Tienes S/{money_str(metrics.business_digital_balance)} digitales en el negocio "
        f"y S/{money_str(metrics.declared_cash_balance)} en efectivo declarado."
    )

    if comparison_text:
        lines.append(f"Comparación: {comparison_text}.")

    if alerts:
        lines.append(f"Aviso: {alerts[0].message}")

    advice = recommend(advice_code) if advice_code in ADVICE else recommend("KEEP_RECORDING")
    lines.append(f"Consejo: {advice['title']}. {advice['body']}")

    if metrics.pending_classifications > 0:
        lines.append(
            f"Hay {metrics.pending_classifications} movimiento(s) sin clasificar; "
            "la lectura de tu semana puede cambiar cuando los aclares."
        )

    if metrics.coverage_status == "NO_DATA":
        lines.append("Aún no hay movimientos registrados en este periodo.")

    lines.append("— Mica · Mi Negocio (demostración)")
    return "\n".join(lines)
