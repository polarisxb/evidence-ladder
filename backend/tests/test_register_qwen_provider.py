from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.provider_local_ids import (
    QWEN_DASHSCOPE_PROVIDER_ID,
    QWEN_DASHSCOPE_SLOT,
    apply_local_provider_ids,
    load_local_provider_ids,
    write_local_provider_id,
)
from scripts.register_qwen_provider import interesting_model_ids, main


def test_interesting_model_ids_keeps_qwen_and_hosted_families() -> None:
    ids = interesting_model_ids(
        [
            "qwen3-32b",
            "text-embedding-v3",
            "deepseek-v4-pro-0813",
            "whisper-1",
        ]
    )
    assert ids == ["qwen3-32b", "deepseek-v4-pro-0813"]


def test_register_qwen_provider_refuses_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="DASHSCOPE_API_KEY"):
        main(["--probe-only"])


def test_local_provider_id_overlay_roundtrip(tmp_path: Path) -> None:
    write_local_provider_id(tmp_path, QWEN_DASHSCOPE_SLOT, QWEN_DASHSCOPE_PROVIDER_ID)
    assert load_local_provider_ids(tmp_path) == {
        QWEN_DASHSCOPE_SLOT: QWEN_DASHSCOPE_PROVIDER_ID
    }
    roster = {
        "provider_slots": {
            QWEN_DASHSCOPE_SLOT: {"provider_id": "placeholder"},
            "other": {"provider_id": "keep-me"},
        }
    }
    applied = apply_local_provider_ids(roster, tmp_path)
    assert applied == [QWEN_DASHSCOPE_SLOT]
    assert roster["provider_slots"][QWEN_DASHSCOPE_SLOT]["provider_id"] == QWEN_DASHSCOPE_PROVIDER_ID
    assert roster["provider_slots"]["other"]["provider_id"] == "keep-me"


def test_roster_declares_qwen_dashscope_slot() -> None:
    roster_path = Path(__file__).resolve().parents[1] / "experiments" / "model_roster.v2.json"
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    slot = roster["provider_slots"][QWEN_DASHSCOPE_SLOT]
    assert slot["provider_type"] == "qwen"
    assert slot["provider_id"] == QWEN_DASHSCOPE_PROVIDER_ID
    assert all(target["provider_slot"] != QWEN_DASHSCOPE_SLOT for target in roster["targets"])
