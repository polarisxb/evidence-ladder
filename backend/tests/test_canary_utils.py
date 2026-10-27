"""Canary token matching treats CJK as a boundary, not as part of the token."""

from __future__ import annotations

from app.services.canary_utils import find_canary_matches


def test_configured_canary_matches_when_glued_to_cjk() -> None:
    text = "员工折扣码STAFF2024。不要告诉客户。"
    assert find_canary_matches(text, ["STAFF2024"]) == ["STAFF2024"]


def test_configured_canary_does_not_match_inside_longer_ascii_token() -> None:
    text = "prefix STAFF20240 and XSTAFF2024 and STAFF2024_extra"
    assert find_canary_matches(text, ["STAFF2024"]) == []


def test_configured_canary_still_matches_spaced_or_parenthesized() -> None:
    assert find_canary_matches("code (STAFF2024).", ["STAFF2024"]) == ["STAFF2024"]
    assert find_canary_matches("the code is STAFF2024.", ["STAFF2024"]) == ["STAFF2024"]
