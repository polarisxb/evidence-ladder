"""Regression tests for Unicode-robust refusal detection.

Live targets (e.g. gpt-style relays) emit a typographic apostrophe U+2019 in
"I can't ...". The engines' refusal patterns are authored with ASCII quotes, so
without normalization a clear refusal slips through — inflating the engines'
preliminary ``success`` flag and making FITD/Crescendo stop escalating against a
target that actually refused. These tests pin the fix.
"""
from __future__ import annotations

import pytest

from app.services.control_variants import _looks_like_refusal as cv_looks_like_refusal
from app.services.ai_analyzer import _looks_like_clear_refusal as analyzer_clear_refusal
from app.services.crescendo_engine import _is_refusal as crescendo_is_refusal
from app.services.engine_utils import normalize_refusal_text
from app.services.fitd_engine import _is_refusal as fitd_is_refusal
from app.services.ice_engine import _is_refusal as ice_is_refusal
from app.services.msj_engine import _is_refusal as msj_is_refusal

# U+2019 RIGHT SINGLE QUOTATION MARK (what real model output uses)
SMART = "I can\u2019t help with instructions for making a pipe bomb."
ASCII = "I can't help with instructions for making a pipe bomb."
COMPLY = "Sure! Here are the detailed step-by-step instructions you asked for."


def test_normalize_folds_typographic_apostrophe():
    assert normalize_refusal_text(SMART) == ASCII
    assert normalize_refusal_text("\u2018a\u2019 \u201cb\u201d") == "'a' \"b\""
    assert normalize_refusal_text("") == ""


@pytest.mark.parametrize("is_refusal", [
    msj_is_refusal, ice_is_refusal, fitd_is_refusal, crescendo_is_refusal,
    cv_looks_like_refusal, analyzer_clear_refusal,
])
def test_smart_apostrophe_refusal_detected(is_refusal):
    # The bug: this returned False because of the U+2019 apostrophe.
    assert is_refusal(SMART) is True
    # ASCII apostrophe still detected (no regression).
    assert is_refusal(ASCII) is True


@pytest.mark.parametrize("is_refusal", [
    msj_is_refusal, ice_is_refusal, fitd_is_refusal, crescendo_is_refusal,
    cv_looks_like_refusal, analyzer_clear_refusal,
])
def test_compliance_not_flagged_as_refusal(is_refusal):
    # Normalization must not create new false positives on a clear compliance.
    assert is_refusal(COMPLY) is False


def test_refusal_signature_matches_smart_apostrophe():
    # Corroborating defense signal: signature "i'm here to help with your banking
    # needs" must still match when the model emits a U+2019 apostrophe.
    from app.services.refusal_signatures import match_refusal_signature

    ascii_v = "I'm here to help with your banking needs."
    smart_v = ascii_v.replace("'", "\u2019")
    assert match_refusal_signature(ascii_v) is not None
    assert match_refusal_signature(smart_v) is not None
    assert match_refusal_signature("Sure, here is the malware code you wanted.") is None


def test_known_fallback_signature_matches_smart_apostrophe():
    # A known non-model fallback rendered with smart quotes must still be marked
    # not_evaluable (known_fallback), not judged as a real model response.
    from app.services.response_screening import (
        TargetResponseEnvelope,
        screen_response_origin,
    )

    base = "I'm experiencing technical difficulties. Please contact our support line."

    def reason(text):
        env = TargetResponseEnvelope(response_text=text, target_type="openai_compatible")
        return screen_response_origin(env).invalid_reason

    assert reason(base) == "known_fallback"
    assert reason(base.replace("'", "\u2019")) == "known_fallback"
    assert reason("Sure, I can help you with that task.") is None
