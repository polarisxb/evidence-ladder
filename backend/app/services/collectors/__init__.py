"""Evidence collectors (Phase 3 of the verdict architecture rollout).

Each ``Collector`` is a pure function on a frozen ``CollectorContext``:
it inspects one slice of the case (rule hits / judge output /
behavior flags / control comparison / refusal signature / business
probe) and returns a ``list[Evidence]``.

Collectors do **not**:

- import each other (everything they need is on ``CollectorContext``)
- mutate any shared state
- decide the final verdict (that is the Phase 4 ``Arbiter``'s job)

This file re-exports the public surface so callers can write
``from app.services.collectors import RuleHitCollector`` without
knowing the internal layout.

Phase 3 is **not wired into production** yet — these classes exist so
Phase 4 ``Arbiter`` can consume them. ``case_executor`` continues to call
the legacy ``classify_verdict``.
"""

from app.services.collectors.base import (
    Collector,
    CollectorContext,
    safe_collect,
)
from app.services.collectors.behavior import BehaviorCollector
from app.services.collectors.control import ControlCollector
from app.services.collectors.judge import JudgeCollector
from app.services.collectors.probe import ProbeCollector
from app.services.collectors.rule_hit import RuleHitCollector
from app.services.collectors.signature import SignatureCollector


# The default ordering used by Phase 4 Arbiter. Hard-evidence
# collectors come first so a future short-circuit optimisation can stop
# early without changing semantics. The order does NOT change the final
# verdict (Arbiter rules are commutative on the evidence chain), it
# only affects the chain's display order.
DEFAULT_COLLECTORS: tuple[Collector, ...] = (
    RuleHitCollector(),
    ProbeCollector(),
    JudgeCollector(),
    BehaviorCollector(),
    ControlCollector(),
    SignatureCollector(),
)


__all__ = [
    "Collector",
    "CollectorContext",
    "safe_collect",
    "BehaviorCollector",
    "ControlCollector",
    "JudgeCollector",
    "ProbeCollector",
    "RuleHitCollector",
    "SignatureCollector",
    "DEFAULT_COLLECTORS",
]
