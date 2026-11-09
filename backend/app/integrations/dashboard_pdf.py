"""Dashboard vectorial: resumen general y una página por billetera seleccionada."""

import math
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

PURPLE = HexColor("#742284")
GREEN = HexColor("#008D78")
CORAL = HexColor("#D85F64")
INK = HexColor("#30243B")
MUTED = HexColor("#726C7C")
PALE = HexColor("#F6F3F8")


def render(document: dict) -> bytes:
    output = BytesIO()
    page = Canvas(output, pagesize=A4, pageCompression=1)
    page.setTitle("Mica · Resumen de tu negocio")
    page.setAuthor("Mica")
    reports = [document, *document.get("wallet_reports", [])]
    for report in reports:
        _draw_page(page, report, len(reports))
    page.save()
    return output.getvalue()


def _draw_page(page: Canvas, document: dict, total_pages: int) -> None:
    width, height = A4
    page.setFillColor(PALE)
    page.rect(0, 0, width, height, stroke=0, fill=1)

    def label(x: float, y: float, value: str, size: int = 10, color=INK, bold=False):
        page.setFillColor(color)
        font = "Helvetica-Bold" if bold else "Helvetica"
        page.setFont(font, size)
        page.drawString(x, y, value)

    def clipped(value: str, maximum: float, size: int = 16) -> str:
        while page.stringWidth(value, "Helvetica-Bold", size) > maximum and len(value) > 1:
            value = value[:-2] + "…"
        return value

    def card(x, y, w, h):
        page.setFillColor(HexColor("#FFFFFF"))
        page.roundRect(x, y, w, h, 14, stroke=0, fill=1)

    def soles(value):
        return f"S/ {Decimal(value):,.2f}"

    page.drawImage(
        str(Path(__file__).parent / "assets" / "mica-logo.png"),
        32,
        height - 58,
        width=64,
        height=48,
        preserveAspectRatio=True,
        mask="auto",
    )
    label(
        112,
        height - 40,
        document.get("section_title")
        or (
            "Tus cuentas, de un vistazo"
            if document.get("includes_personal")
            else "Tu negocio, de un vistazo"
        ),
        17,
        INK,
        True,
    )
    label(32, height - 79, clipped(" · ".join(document["wallet_names"]), width - 64), 16, INK, True)
    start = date.fromisoformat(document["start"]).strftime("%d/%m/%Y")
    end = date.fromisoformat(document["end"]).strftime("%d/%m/%Y")
    label(32, height - 96, f"{start}  —  {end}", 11, MUTED)
    for index, (name, key, color) in enumerate(
        (("INGRESOS", "income", GREEN), ("EGRESOS", "expense", CORAL), ("RESULTADO", "net", PURPLE))
    ):
        x = 32 + index * 181
        card(x, 635, 169, 86)
        label(x + 13, 695, name, 10, MUTED, True)
        amount = soles(document[key])
        size = 20
        while page.stringWidth(amount, "Helvetica-Bold", size) > 145 and size > 10:
            size -= 1
        label(x + 13, 660, amount, size, color, True)
    card(32, 338, width - 64, 277)
    label(50, 590, "Ingresos y egresos en el tiempo", 13, INK, True)
    label(50, 572, "Importes en soles · agrupados por fecha", 9, MUTED)
    days = document["days"]
    step = max(1, math.ceil(len(days) / 10))
    groups = [days[i : i + step] for i in range(0, len(days), step)]
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 35, 35, 447, 153
    chart.data = [
        [float(sum((Decimal(d[key]) for d in group), Decimal("0"))) for group in groups]
        for key in ("income", "expense")
    ]
    chart.categoryAxis.categoryNames = [
        date.fromisoformat(g[0]["day"]).strftime("%d/%m") for g in groups
    ]
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontSize = 8
    values = [v for series in chart.data for v in series]
    chart.valueAxis.valueMin = min(0, min(values, default=0))
    chart.valueAxis.valueMax = max(1, max(values, default=1)) * 1.15
    chart.bars[0].fillColor, chart.bars[1].fillColor = GREEN, CORAL
    chart.bars.strokeColor = None
    chart.groupSpacing = 5
    drawing = Drawing(500, 215)
    drawing.add(chart)
    renderPDF.draw(drawing, page, 48, 357)
    label(70, 356, "Ingresos", 9, GREEN, True)
    label(155, 356, "Egresos", 9, CORAL, True)
    card(32, 117, width - 64, 204)
    label(50, 295, "Efectivo y digital, por separado", 13, INK, True)
    medium = HorizontalBarChart()
    medium.x, medium.y, medium.width, medium.height = 75, 28, 395, 89
    medium.data = [
        [float(document["media"][m][key]) for m in ("DIGITAL", "CASH")]
        for key in ("income", "expense")
    ]
    medium.categoryAxis.categoryNames = ["Digital", "Efectivo"]
    medium.categoryAxis.labels.fontSize = 10
    medium.valueAxis.labels.fontSize = 8
    medium.valueAxis.valueMin = min(0, min(v for series in medium.data for v in series))
    medium.valueAxis.valueMax = max(1, max(v for series in medium.data for v in series)) * 1.12
    medium.bars[0].fillColor, medium.bars[1].fillColor = GREEN, CORAL
    medium.bars.strokeColor = None
    drawing = Drawing(500, 150)
    drawing.add(medium)
    renderPDF.draw(drawing, page, 48, 146)
    for i, (name, key) in enumerate((("Efectivo", "CASH"), ("Digital", "DIGITAL"))):
        values = document["media"][key]
        label(
            50 + i * 260,
            135,
            f"{name}: +{soles(values['income'])} / -{soles(values['expense'])}",
            9,
        )
    if document.get("empty"):
        label(50, 319, "Sin movimientos para este periodo.", 10, MUTED)
    label(
        33,
        94,
        "No incluye aperturas ni transferencias entre billeteras."
        if document.get("includes_personal")
        else "No incluye aperturas, transferencias entre billeteras ni gastos personales.",
        8,
        MUTED,
    )
    label(
        33,
        80,
        "Digital: libro disponible; si no hay datos del día, última declaración confirmada.",
        8,
        MUTED,
    )
    label(
        33,
        66,
        "Las declaraciones sustituidas no se suman. Resultado = ingresos menos egresos.",
        8,
        MUTED,
    )
    if Decimal(document.get("declared_digital", "0")):
        label(
            33,
            49,
            f"Incluye {soles(document['declared_digital'])} digitales informados por ti, sin conciliación bancaria.",
            8,
            PURPLE,
        )
    label(540, 25, f"{page.getPageNumber()} / {total_pages}", 8, MUTED)
    page.showPage()
