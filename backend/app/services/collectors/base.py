"""Collector base abstractions.

A ``Collector`` is a small, single-responsibility unit that emits
``Evidence`` from a frozen view of one case. It is the building block of
the Phase 4 Arbiter.

Two design rules enforced here:

1. **Total inputs**: a Collector must read everything it needs from
   ``CollectorContext``. It must not import other Collectors, the legacy
   ``classify_verdict``, the Arbiter, or any module-level mutable state.
2. **Total fault tolerance**: a Collector that raises must not break the
   pipeline. ``safe_collect`` is the wrapper the Arbiter uses to enforce
   this. Tests assert both halves.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.schemas.report import AnalysisResult
from app.services.evidence import Evidence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectorContext:
    """All the inputs a Collector may inspect.

    Frozen because Collectors must not mutate shared state. If a future
    Collector needs an extra signal, add a field here — never read from
    a global.

    Field naming mirrors what the legacy ``classify_verdict`` already
    receives, plus the two new fields (``business_verification_status``
    and ``response_evaluation``) that Phase 4 Arbiter R3 needs.
    """

    attack_payload: str
    target_response: str
    analysis: AnalysisResult
    target_config: Mapping[str, Any] | None = None
    control_assessment: str | None = None
    business_verification_status: str | None = None
    response_evaluation: Mapping[str, Any] | None = None


class Collector(ABC):
    """Single-responsibility evidence emitter.

    Subclasses set ``source`` to the ``EvidenceSource`` literal they
    primarily emit (used for logging and Arbiter routing) and implement
    :meth:`collect`.
    """

    source: str = ""  # subclasses override

    @abstractmethod
    def collect(self, ctx: CollectorContext) -> list[Evidence]:
        """Inspect ``ctx`` and emit zero or more ``Evidence`` objects.

        A Collector returns an empty list (never ``None``) when it has
        nothing to say about the case. It must not raise for benign
        "no signal" inputs — only for genuine programming errors.
        """


def safe_collect(collector: Collector, ctx: CollectorContext) -> list[Evidence]:
    """Run a Collector with a hard try/except guard.

    The Arbiter uses this to keep one buggy Collector from killing the
    whole verdict. A failing Collector is logged and treated as if it
    emitted nothing — Arbiter R7 (weak signals) then kicks in if no
    other Collector covered the ground.

    Returns an empty list on any exception; never re-raises.
    """

    try:
        result = collector.collect(ctx)
    except Exception as exc:  # pragma: no cover - exercised via test
        logger.warning(
            "Collector %s raised %s: %s",
            collector.__class__.__name__,
            exc.__class__.__name__,
            exc,
        )
        return []

    if result is None:
        # Defensive: treat ``None`` like an empty list. We do not want
        # the Arbiter to ever see ``None`` in its evidence chain.
        return []

    return list(result)
