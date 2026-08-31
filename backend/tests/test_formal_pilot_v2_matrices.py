"""Smoke tests for formal-pilot v2 model roster matrices."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.experiment_driver import ModelMatrixConfig


_EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"


def _load(name: str) -> ModelMatrixConfig:
    raw = json.loads((_EXPERIMENTS / name).read_text(encoding="utf-8"))
    return ModelMatrixConfig.model_validate(raw)


def test_v2_full_matrices_have_three_targets_and_distinct_judge_providers() -> None:
    for filename in (
        "formal_pilot_v2_jclaude_vgemini_models.json",
        "formal_pilot_v2_jgemini_vclaude_models.json",
    ):
        matrix = _load(filename)
        assert len(matrix.target_models) == 3
        assert matrix.judge_model.provider_id != matrix.verifier_model.provider_id
        assert matrix.judge_model.pinned_version != matrix.verifier_model.pinned_version


def test_v2_paid_gate_matrix_single_target() -> None:
    matrix = _load("stateful_paid_gate_v2_models.json")
    assert len(matrix.target_models) == 1
    assert matrix.target_models[0].pinned_version == "gpt-5.5-2026-04-23"
