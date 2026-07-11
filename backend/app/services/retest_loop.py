# backend/app/services/retest_loop.py
from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceDelta:
    """One retest action's evidence contribution.

    ``evidence_updates`` are merged into the result mapping and re-arbitrated.
    ``contradiction`` is an explicit signal (e.g., the quoted control also
    "succeeded") that the arbiter cannot derive from the attack result alone.
    """

    action_type: str
    evidence_updates: Mapping[str, Any] = field(default_factory=dict)
    contradiction: bool = False
    extra_queries: int = 0
    extra_cost_ms: float = 0.0
    summary: str = ""


def merge_evidence(result: Mapping[str, Any], delta: EvidenceDelta) -> dict[str, Any]:
    """Return a new result with ``delta.evidence_updates`` merged in (pure).

    Nested mappings are shallow-merged one level; other keys are replaced.
    """
    merged = copy.deepcopy(dict(result))
    for key, value in delta.evidence_updates.items():
        existing = merged.get(key)
        if isinstance(value, Mapping) and isinstance(existing, Mapping):
            nested = dict(existing)
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged
