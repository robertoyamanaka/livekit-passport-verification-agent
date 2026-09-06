"""Tests for agent.py's _parse_dispatch_metadata — the job-dispatch JSON
parsed at the start of every call (customer_name/email come from here)."""

from agent import _parse_dispatch_metadata


def test_empty_string_returns_empty_dict():
    assert _parse_dispatch_metadata("") == {}


def test_valid_object_is_parsed():
    assert _parse_dispatch_metadata('{"customer_name": "Roberto", "email": "r@x.com"}') == {
        "customer_name": "Roberto",
        "email": "r@x.com",
    }


def test_invalid_json_returns_empty_dict():
    assert _parse_dispatch_metadata("not json at all") == {}


def test_non_object_json_returns_empty_dict():
    # Valid JSON, but not the object shape the caller expects.
    assert _parse_dispatch_metadata("[1, 2, 3]") == {}
    assert _parse_dispatch_metadata("42") == {}
    assert _parse_dispatch_metadata('"just a string"') == {}


def test_non_string_values_are_coerced_to_str():
    # Guards the declared dict[str, str] return type actually being true,
    # instead of a nested number/bool silently flowing through untyped.
    result = _parse_dispatch_metadata('{"retries": 3, "urgent": true}')
    assert result == {"retries": "3", "urgent": "True"}
