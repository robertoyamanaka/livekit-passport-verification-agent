"""Contract copy + PDF rendering for the in-call e-signature step.

The contract text is generated once here and reused verbatim for both the
`contract_ready` event the browser renders and the PDF that actually gets
emailed after signing — a single source of truth, so what the customer reads
on screen can never drift from what they end up signing.

Uses reportlab's platypus flowables (not raw canvas coordinate math) so the
signature block lays out correctly regardless of how long the terms text
runs — flowables auto-paginate.
"""

from __future__ import annotations

import io
import time

from reportlab.graphics.shapes import Drawing, Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FINANCE_CO_NAME = "Meridiano Auto Finance"
VEHICLE = "Ford Mustang"
AMOUNT_FINANCED = "$38,500.00 USD"
# Printed name for the finance company's side of the signature block. There's
# no real back-office signer behind this demo, so this is a fixed placeholder
# — see _dummy_representative_signature() for the matching drawn scribble.
REPRESENTATIVE_NAME = "Marcela Duarte"


def _dummy_representative_signature(width: float = 2.5 * inch, height: float = 0.9 * inch) -> Drawing:
    """A small drawn scribble standing in for the finance company's
    authorized-representative signature, so the PDF's signature block isn't
    lopsided with only the customer's side filled in. Built as vector shapes
    (not a bundled image asset) — cheap, dependency-free, and resizes cleanly
    alongside the customer's actual signature image next to it."""
    ink = colors.HexColor("#16223b")
    drawing = Drawing(width, height)

    stroke = Path(strokeColor=ink, strokeWidth=1.8, fillColor=None, strokeLineCap=1)
    stroke.moveTo(12, 24)
    stroke.curveTo(26, 58, 38, 6, 54, 36)
    stroke.curveTo(66, 58, 80, 10, 94, 32)
    stroke.curveTo(103, 45, 112, 20, 126, 30)
    stroke.lineTo(158, 30)
    drawing.add(stroke)

    flourish = Path(strokeColor=ink, strokeWidth=1.1, fillColor=None, strokeLineCap=1)
    flourish.moveTo(14, 13)
    flourish.curveTo(62, 2, 122, 2, 164, 15)
    drawing.add(flourish)

    return drawing


def new_contract_number() -> str:
    return f"MAF-{int(time.time())}"


def render_contract(
    *,
    contract_number: str,
    customer_name: str,
    document_number: str,
) -> list[str]:
    """Returns the final contract body as a list of paragraphs. This exact
    text is what both the browser and the emailed PDF display — see the
    module docstring."""
    return [
        f"Contrato de Financiamiento Vehicular N.° {contract_number}, celebrado entre "
        f"{FINANCE_CO_NAME} (“la Financiera”) y {customer_name}, identificado con "
        f"documento N.° {document_number} (“el Cliente”).",
        f"1. OBJETO. La Financiera otorga al Cliente un financiamiento para la adquisición "
        f"de un vehículo {VEHICLE} 0KM, por un monto total de {AMOUNT_FINANCED}, sujeto a "
        "los términos y condiciones aquí descritos.",
        "2. PLAZO Y PAGOS. El financiamiento se pagará en cuotas mensuales iguales y "
        "consecutivas, de acuerdo con el plan de pagos entregado al Cliente al momento de "
        "la aprobación del crédito.",
        "3. ENTREGA DEL VEHÍCULO. Una vez firmado este contrato, el Cliente podrá "
        "acercarse a la agencia con una copia del presente documento para coordinar la "
        "entrega del vehículo.",
        "4. VERIFICACIÓN DE IDENTIDAD. El Cliente confirma que su identidad fue validada "
        "durante la llamada de cierre mediante la presentación de un documento oficial, "
        "cuyos datos coinciden con los aquí consignados.",
        "5. ACEPTACIÓN. Al firmar electrónicamente este documento, el Cliente declara "
        "haber leído y aceptado la totalidad de los términos anteriores.",
    ]


def build_signed_contract_pdf(
    *,
    contract_number: str,
    customer_name: str,
    paragraphs: list[str],
    typed_name: str,
    signature_png_bytes: bytes,
    signed_at_ms: int,
) -> bytes:
    """Renders the final, signed contract as PDF bytes, ready to attach to
    an email."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=16,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ContractSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=20,
    )
    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=15,
        spaceAfter=12,
    )
    signature_label_style = ParagraphStyle(
        "SignatureLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
    )
    signature_name_style = ParagraphStyle(
        "SignatureName",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=13,
    )

    signed_at = time.strftime("%d/%m/%Y %H:%M", time.localtime(signed_at_ms / 1000))

    story = [
        Paragraph(FINANCE_CO_NAME, title_style),
        Paragraph(f"Contrato de Financiamiento Vehicular &mdash; N.° {contract_number}", subtitle_style),
    ]
    for paragraph in paragraphs:
        story.append(Paragraph(paragraph, body_style))

    story.append(Spacer(1, 0.35 * inch))

    signature_image = Image(io.BytesIO(signature_png_bytes), width=2.5 * inch, height=0.9 * inch)
    signature_block = Table(
        [
            [signature_image, _dummy_representative_signature()],
            [Paragraph(typed_name, signature_name_style), Paragraph(REPRESENTATIVE_NAME, signature_name_style)],
            [
                Paragraph(f"Firma del Cliente &mdash; {signed_at}", signature_label_style),
                Paragraph("Representante autorizado", signature_label_style),
            ],
        ],
        colWidths=[3 * inch, 3 * inch],
    )
    signature_block.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 1), (0, 1), 0.75, colors.HexColor("#333333")),
                ("LINEABOVE", (1, 1), (1, 1), 0.75, colors.HexColor("#333333")),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ]
        )
    )
    story.append(signature_block)

    doc.build(story)
    return buffer.getvalue()
