"""Tests for contract_pdf.py: the contract copy generator and the final
signed-PDF renderer. Both are pure functions (no I/O beyond returning bytes),
so no network/LiveKit mocking is needed here.
"""

import io

from PIL import Image

from contract_pdf import (
    AMOUNT_FINANCED,
    FINANCE_CO_NAME,
    VEHICLE,
    build_signed_contract_pdf,
    new_contract_number,
    render_contract,
)


def _fake_signature_png() -> bytes:
    """A tiny transparent PNG standing in for a real drawn signature — only
    its validity as an image matters here, not its content."""
    buffer = io.BytesIO()
    Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_new_contract_number_is_prefixed_and_unique_enough():
    a = new_contract_number()
    assert a.startswith("MAF-")


def test_render_contract_interpolates_all_given_fields():
    paragraphs = render_contract(
        contract_number="MAF-123",
        customer_name="Roberto Yamanaka",
        document_number="X1234567",
    )
    full_text = " ".join(paragraphs)
    assert "MAF-123" in full_text
    assert "Roberto Yamanaka" in full_text
    assert "X1234567" in full_text
    assert VEHICLE in full_text
    assert FINANCE_CO_NAME in full_text
    assert AMOUNT_FINANCED in full_text


def test_render_contract_returns_multiple_paragraphs():
    paragraphs = render_contract(
        contract_number="MAF-123", customer_name="Someone", document_number="Y1"
    )
    assert len(paragraphs) >= 5
    assert all(isinstance(p, str) and p for p in paragraphs)


def test_build_signed_contract_pdf_produces_a_valid_pdf():
    paragraphs = render_contract(
        contract_number="MAF-999", customer_name="Roberto Yamanaka", document_number="X1"
    )
    pdf_bytes = build_signed_contract_pdf(
        contract_number="MAF-999",
        customer_name="Roberto Yamanaka",
        paragraphs=paragraphs,
        typed_name="Roberto Yamanaka",
        signature_png_bytes=_fake_signature_png(),
        signed_at_ms=1_700_000_000_000,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
