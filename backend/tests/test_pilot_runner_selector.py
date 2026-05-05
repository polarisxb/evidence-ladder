from __future__ import annotations

from collections import Counter

import pytest

from app.services.pilot_runner import (
    PREFERRED_PILOT_CATEGORIES,
    load_attack_template_bundles,
    select_pilot_cases,
)


def test_default_selector_returns_30_cases_balanced_across_six_categories() -> None:
    bundles = load_attack_template_bundles()

    cases = select_pilot_cases(bundles, case_count=30, seed=20260504)

    assert len(cases) == 30
    counts = Counter(case.category for case in cases)
    assert list(counts) == list(PREFERRED_PILOT_CATEGORIES)
    assert counts == {category: 5 for category in PREFERRED_PILOT_CATEGORIES}


def test_selector_uses_stable_case_ids_and_payload_indexes() -> None:
    bundles = load_attack_template_bundles()

    cases = select_pilot_cases(bundles, case_count=6, seed=20260504)

    assert [case.case_id for case in cases] == [
        "PI-001:0",
        "SP-001:0",
        "JB-001:0",
        "ID-001:0",
        "II-001:0",
        "EA-001:0",
    ]
    assert [case.payload_index for case in cases] == [0, 0, 0, 0, 0, 0]


def test_selector_is_deterministic_for_same_input_and_seed() -> None:
    bundles = load_attack_template_bundles()

    first = select_pilot_cases(bundles, case_count=30, seed=20260504)
    second = select_pilot_cases(bundles, case_count=30, seed=20260504)

    assert first == second


def test_selector_rejects_unsatisfied_case_count() -> None:
    bundles = [
        {
            "category": "prompt_injection",
            "owasp_id": "LLM01",
            "templates": [
                {
                    "id": "PI-X",
                    "name": "Tiny fixture",
                    "payloads": [
                        {"text": "one", "language": "en", "variant": "base"},
                    ],
                }
            ],
        }
    ]

    with pytest.raises(ValueError, match="requested case count"):
        select_pilot_cases(bundles, case_count=2, seed=20260504)
