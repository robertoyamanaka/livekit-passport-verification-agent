"""Sends the signed contract PDF to the customer via Resend.

Kept in its own module so agent.py's tool logic stays readable, and so this
piece is easy to unit-test in isolation (see agent/tests/test_contract_email.py,
which mocks the `resend` module — no network call). The PDF itself is built by
contract_pdf.py — this module only knows how to mail whatever bytes it's handed.
"""

from __future__ import annotations

import logging
import os

import resend

from contract_pdf import FINANCE_CO_NAME, VEHICLE

logger = logging.getLogger("passport-verification-agent.email")

# yamanaka.io is a verified sending domain in Resend, so this can deliver to
# any recipient — not just the account's own address (the onboarding@resend.dev
# sandbox sender is restricted to that).
SENDER = f"{FINANCE_CO_NAME} <contratos@yamanaka.io>"


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
            "subject": f"Tu contrato firmado — {VEHICLE}",
            "html": _build_email_html(customer_name),
            "attachments": [
                {
                    # This SDK version expects raw bytes as a list of ints,
                    # not a base64 string — see resend.emails._attachment.Attachment.
                    # The PDF is only a few KB, so the ~8x memory overhead of
                    # boxing every byte into a Python int isn't worth working
                    # around; not worth it at a much larger size either.
                    "filename": _attachment_filename(),
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


def _attachment_filename() -> str:
    slug = VEHICLE.lower().replace(" ", "_")
    return f"contrato_financiamiento_{slug}_firmado.pdf"


def _build_email_html(customer_name: str) -> str:
    return f"""
    <div style="font-family: -apple-system, Helvetica, Arial, sans-serif;
                color:#0f172a; line-height:1.5;">
      <p>Hola {customer_name},</p>
      <p>
        Gracias por confirmar tu identidad y firmar tu contrato durante
        nuestra llamada. Adjunto encontrarás la copia firmada del contrato de
        financiamiento para tu {VEHICLE}.
      </p>
      <p>
        Guarda una copia y tráela a la agencia para coordinar la entrega de
        tu vehículo.
      </p>
      <p>Saludos cordiales,<br />{FINANCE_CO_NAME}</p>
    </div>
    """
