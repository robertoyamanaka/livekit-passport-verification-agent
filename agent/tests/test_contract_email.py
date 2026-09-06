"""Tests for contract_email.py, with the resend module mocked out — no
network call is ever made here. Covers the success/failure paths and locks
in the single-source-of-truth fix (subject/sender/body must use the
VEHICLE/FINANCE_CO_NAME constants, not a hardcoded restatement of them).
"""

import resend

import contract_email
from contract_pdf import FINANCE_CO_NAME, VEHICLE


async def test_send_contract_email_success(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    sent_params = {}

    async def fake_send_async(params):
        sent_params.update(params)
        return {"id": "fake-email-id"}

    monkeypatch.setattr(resend.Emails, "send_async", fake_send_async)

    result = await contract_email.send_contract_email(
        "Roberto Yamanaka", "roberto@example.com", b"%PDF-fake-bytes"
    )

    assert result is True
    assert sent_params["to"] == ["roberto@example.com"]
    assert VEHICLE in sent_params["subject"]
    assert FINANCE_CO_NAME in sent_params["from"]
    assert FINANCE_CO_NAME in sent_params["html"]
    assert sent_params["attachments"][0]["content"] == list(b"%PDF-fake-bytes")


async def test_send_contract_email_missing_api_key_returns_false(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    result = await contract_email.send_contract_email("Roberto", "r@example.com", b"pdf")

    assert result is False


async def test_send_contract_email_sdk_failure_returns_false_not_raise(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")

    async def failing_send_async(params):
        raise RuntimeError("Resend API is down")

    monkeypatch.setattr(resend.Emails, "send_async", failing_send_async)

    result = await contract_email.send_contract_email("Roberto", "r@example.com", b"pdf")

    assert result is False
