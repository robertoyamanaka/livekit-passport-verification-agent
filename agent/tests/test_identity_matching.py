"""Tests for agent.py's mocked identity-verification logic: _normalize_name,
names_match, and _tokens_close. This is the exact logic a live call exercises
when a customer shows a passport with a different name — covered here without
needing an actual call.
"""

from agent import _normalize_name, _tokens_close, names_match


def test_normalize_name_lowercases_and_strips_accents():
    assert _normalize_name("Roberto Yamanaka") == "roberto yamanaka"
    assert _normalize_name("José Núñez") == "jose nunez"


def test_normalize_name_collapses_whitespace():
    assert _normalize_name("  Ana   María  ") == "ana maria"


def test_names_match_exact():
    assert names_match("Roberto Yamanaka", "Roberto Yamanaka") is True


def test_names_match_case_and_accent_insensitive():
    assert names_match("José Núñez", "JOSE NUNEZ") is True


def test_names_match_tolerates_a_small_typo():
    # One transposed letter — within the fuzzy-match threshold.
    assert names_match("Roberto Yamanaka", "Roberto Yamanka") is True


def test_names_match_token_order_independent():
    assert names_match("Yamanaka Roberto", "Roberto Yamanaka") is True


def test_names_match_rejects_a_genuine_mismatch():
    # Same surname, different first name — the exact case this matching
    # strategy (token-by-token, not whole-string ratio) exists to get right.
    assert names_match("Michael Corleone", "Fredo Corleone") is False


def test_names_match_rejects_an_unrelated_name():
    assert names_match("Roberto Yamanaka", "Someone Else") is False


def test_names_match_empty_input_never_matches():
    assert names_match("", "Roberto Yamanaka") is False
    assert names_match("Roberto Yamanaka", "") is False
    assert names_match("", "") is False


def test_tokens_close_respects_threshold():
    assert _tokens_close("roberto", "roberto") is True
    assert _tokens_close("roberto", "xxxxxxx") is False
