"""Local, untracked provider UUID overlays.

The committed roster keeps placeholder UUIDs until a key is registered in
the operator's own database. This helper reads/writes
``experiments/.provider_ids.local.json`` so a laptop can rebuild matrices
against real DB ids without committing secrets or leaking keys.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LOCAL_IDS_NAME = ".provider_ids.local.json"

# Frozen slot id for the DashScope / 千问云 provider. The register script
# upserts this exact row so a later T1 rematrix does not need a new UUID.
QWEN_DASHSCOPE_SLOT = "qwen-dashscope"
QWEN_DASHSCOPE_PROVIDER_ID = "22222222-2222-4222-8222-222222220004"


def local_ids_path(experiments_dir: Path) -> Path:
    return experiments_dir / LOCAL_IDS_NAME


def load_local_provider_ids(experiments_dir: Path) -> dict[str, str]:
    path = local_ids_path(experiments_dir)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must be a JSON object of slot -> uuid")
    return {
        str(slot): str(provider_id)
        for slot, provider_id in raw.items()
        if str(slot).strip() and str(provider_id).strip()
    }


def write_local_provider_id(
    experiments_dir: Path,
    slot: str,
    provider_id: str,
) -> Path:
    path = local_ids_path(experiments_dir)
    data = load_local_provider_ids(experiments_dir)
    data[slot] = provider_id
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def apply_local_provider_ids(roster: dict[str, Any], experiments_dir: Path) -> list[str]:
    overlays = load_local_provider_ids(experiments_dir)
    applied: list[str] = []
    slots = roster.get("provider_slots") or {}
    for slot, provider_id in overlays.items():
        if slot not in slots:
            continue
        slots[slot]["provider_id"] = provider_id
        applied.append(slot)
    return applied
