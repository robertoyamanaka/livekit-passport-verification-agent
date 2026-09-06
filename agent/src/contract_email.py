"""Sends the signed contract PDF to the customer via Resend.

Kept in its own module so agent.py's tool logic stays readable, and so this
piece can be tested in isolation (`python -m src.contract_email` below). The
PDF itself is built by contract_pdf.py — this module only knows how to mail
whatever bytes it's handed.
"""

from __future__ import annotations

import logging
import os

import resend

logger = logging.getLogger("passport-verification-agent.email")

# yamanaka.io is a verified sending domain in Resend, so this can deliver to
# any recipient — not just the account's own address (the onboarding@resend.dev
# sandbox sender is restricted to that).
SENDER = "Meridiano Auto Finance <contratos@yamanaka.io>"


async def send_contract_email(customer_name: str, customer_email: str, pdf_bytes: bytes) -> bool:
    """Sends the contract email with the given signed-contract PDF attached.
    Returns True on success, False on any failure — this must never raise,
    so the caller can fall back to a graceful spoken line instead of the
    call breaking.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY is not set; skipping contract email")
        return False

    resend.api_key = api_key

    try:
        params: resend.Emails.SendParams = {
            "from": SENDER,
            "to": [customer_email],
            "subject": "Tu contrato firmado — Ford Mustang",
            "html": _build_email_html(customer_name),
            "attachments": [
                {
                    # This SDK version expects raw bytes as a list of ints,
                    # not a base64 string — see resend.emails._attachment.Attachment.
                    "filename": "contrato_financiamiento_mustang_firmado.pdf",
                    "content": list(pdf_bytes),
                }
            ],
        }
        await resend.Emails.send_async(params)
        logger.info("Contract email sent to %s", customer_email)
        return True
    except Exception:
        logger.exception("Failed to send contract email via Resend")
        return False


def _build_email_html(customer_name: str) -> str:
    return f"""
    <div style="font-family: -apple-system, Helvetica, Arial, sans-serif; color:#0f172a; line-height:1.5;">
      <p>Hola {customer_name},</p>
      <p>
        Gracias por confirmar tu identidad y firmar tu contrato durante
        nuestra llamada. Adjunto encontrarás la copia firmada del contrato de
        financiamiento para tu Ford Mustang.
      </p>
      <p>
        Guarda una copia y tráela a la agencia para coordinar la entrega de
        tu vehículo.
      </p>
      <p>Saludos cordiales,<br />Meridiano Auto Finance</p>
    </div>
    """
