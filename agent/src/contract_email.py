"""Sends the mock signed-pending contract PDF to the customer via Resend.

Kept in its own module so agent.py's tool logic stays readable, and so this
piece can be tested in isolation (`python -m src.contract_email` below).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import resend

logger = logging.getLogger("passport-verification-agent.email")

CONTRACT_PDF_PATH = Path(__file__).resolve().parent.parent / "assets" / "mock_contract.pdf"
SENDER = "Meridiano Auto Finance <onboarding@resend.dev>"


async def send_contract_email(customer_name: str, customer_email: str) -> bool:
    """Sends the contract email. Returns True on success, False on any
    failure — this must never raise, so the caller can fall back to a
    graceful spoken line instead of the call breaking.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY is not set; skipping contract email")
        return False

    if not CONTRACT_PDF_PATH.exists():
        logger.error("Mock contract PDF not found at %s; skipping email", CONTRACT_PDF_PATH)
        return False

    resend.api_key = api_key

    try:
        pdf_bytes = CONTRACT_PDF_PATH.read_bytes()
        params: resend.Emails.SendParams = {
            "from": SENDER,
            "to": [customer_email],
            "subject": "Tu contrato de financiamiento — Ford Mustang",
            "html": _build_email_html(customer_name),
            "attachments": [
                {
                    # This SDK version expects raw bytes as a list of ints,
                    # not a base64 string — see resend.emails._attachment.Attachment.
                    "filename": "contrato_financiamiento_mustang.pdf",
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
        Gracias por confirmar tu identidad durante nuestra llamada. Adjunto
        encontrarás el contrato de financiamiento para tu Ford Mustang.
      </p>
      <p>
        Por favor revísalo con calma y, una vez firmado, tráelo a la agencia
        para coordinar la entrega de tu vehículo.
      </p>
      <p>Saludos cordiales,<br />Meridiano Auto Finance</p>
    </div>
    """
