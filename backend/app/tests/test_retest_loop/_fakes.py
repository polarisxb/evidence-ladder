# backend/app/tests/test_retest_loop/_fakes.py
from collections.abc import Mapping
from typing import Any

from app.services.retest_loop import EvidenceDelta


class FakeRetestExecutor:
    """Scripted executor: each method pops the next queued EvidenceDelta.

    A no-op delta (empty updates) simulates "retest gathered nothing new".
    """

    def __init__(self, *, quartet=None, canary=None, probe=None):
        self._q = list(quartet or [])
        self._c = list(canary or [])
        self._p = list(probe or [])

    def _next(self, queue, action_type):
        if queue:
            return queue.pop(0)
        return EvidenceDelta(action_type=action_type, summary="no-op")

    def run_quartet(self, result: Mapping[str, Any]) -> EvidenceDelta:
        return self._next(self._q, "run_quartet")

    def run_canary(self, result: Mapping[str, Any]) -> EvidenceDelta:
        return self._next(self._c, "run_canary")

    def run_probe(self, result: Mapping[str, Any]) -> EvidenceDelta:
        return self._next(self._p, "run_probe")


class AsyncFakeRetestExecutor(FakeRetestExecutor):
    """Async twin of :class:`FakeRetestExecutor` for ``run_retest_loop_async``."""

    async def run_quartet(self, result: Mapping[str, Any]) -> EvidenceDelta:
        return self._next(self._q, "run_quartet")

    async def run_canary(self, result: Mapping[str, Any]) -> EvidenceDelta:
        return self._next(self._c, "run_canary")

    async def run_probe(self, result: Mapping[str, Any]) -> EvidenceDelta:
        return self._next(self._p, "run_probe")
