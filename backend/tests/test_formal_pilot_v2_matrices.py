"""Smoke tests for formal-pilot v2.3 (domestic-first, live-id refresh) matrices."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.experiment_driver import ModelMatrixConfig

_EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"

_FULL_MATRICES = (
    "formal_pilot_v2_jdeepseek_vglm_models.json",
    "formal_pilot_v2_jglm_vdeepseek_models.json",
)

# Phase-1 is domestic-only; frontier-US ids belong to the expansion roster.
_PHASE2_ONLY_MARKERS = ("gpt-", "claude", "gemini")


def _load(name: str) -> ModelMatrixConfig:
    raw = json.loads((_EXPERIMENTS / name).read_text(encoding="utf-8"))
    return ModelMatrixConfig.model_validate(raw)


def test_v2_full_matrices_have_three_targets_and_distinct_judge_providers() -> None:
    for filename in _FULL_MATRICES:
        matrix = _load(filename)
        assert len(matrix.target_models) == 3
        assert matrix.judge_model.provider_id != matrix.verifier_model.provider_id
        assert matrix.judge_model.pinned_version != matrix.verifier_model.pinned_version


def test_v2_matrices_are_role_swapped_pair() -> None:
    matrix_a = _load(_FULL_MATRICES[0])
    matrix_b = _load(_FULL_MATRICES[1])
    assert matrix_a.judge_model.pinned_version == matrix_b.verifier_model.pinned_version
    assert matrix_a.verifier_model.pinned_version == matrix_b.judge_model.pinned_version


def test_v2_phase1_matrices_are_domestic_only() -> None:
    for filename in (*_FULL_MATRICES, "stateful_paid_gate_v2_models.json"):
        matrix = _load(filename)
        for model in matrix.models:
            version = model.pinned_version.lower()
            assert not any(marker in version for marker in _PHASE2_ONLY_MARKERS), (
                f"{filename}: {model.pinned_version!r} belongs to the Phase-2 "
                "expansion roster, not the domestic-first Phase-1 matrices"
            )


def test_v2_paid_gate_matrix_single_target() -> None:
    matrix = _load("stateful_paid_gate_v2_models.json")
    assert len(matrix.target_models) == 1
    assert matrix.target_models[0].pinned_version == "kimi-k2.6"
    # The single gate run must exercise all three provider keys.
    provider_ids = {
        matrix.target_models[0].provider_id,
        matrix.judge_model.provider_id,
        matrix.verifier_model.provider_id,
    }
    assert len(provider_ids) == 3
