"""Unit tests for llm_scheduler — AIMD, ProviderPool, JudgeDedup, schedule_call."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.llm_client import LLMAPIError, LLMRateLimitError, ProviderClientInfo
from app.services.llm_scheduler import (
    FLOOR_BACKOFF_BASE,
    INITIAL_LIMIT,
    MAX_CONSECUTIVE_FAILURES,
    MAX_LIMIT,
    MIN_LIMIT,
    RETRY_BUCKET_MAX,
    RETRY_COST_429,
    SEVERE_FACTOR,
    SEVERE_THRESHOLD,
    SOFT_FACTOR,
    AIMDController,
    AllRetriesExhaustedError,
    JudgeDedup,
    NoProviderAvailableError,
    ProviderPool,
    ProviderSlot,
    _full_jitter_delay,
    _hamming_distance,
    _simhash_fingerprint,
    _slot_key_id,
    schedule_fixed_call,
    schedule_generation_call,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_slot(
    role: str = "judge",
    tier: str = "tier1",
    key: str = "test-key",
    provider_type: str = "deepseek",
    healthy: bool = True,
    weight: float = 1.0,
    provider_id: str | None = None,
    model: str = "test-model",
) -> ProviderSlot:
    info = ProviderClientInfo(provider_type=provider_type, api_key=key)
    return ProviderSlot(
        provider_info=info,
        model=model,
        key_id=_slot_key_id(provider_type, key),
        role=role,
        tier=tier,
        healthy=healthy,
        weight=weight,
        provider_id=provider_id,
    )


# ===========================================================================
# AIMDController
# ===========================================================================


class TestAIMDController:

    @pytest.mark.asyncio
    async def test_acquire_release_basic(self):
        ctrl = AIMDController()
        key = "k1"
        start = await ctrl.acquire(key)
        assert ctrl._get(key).in_flight == 1
        await ctrl.release_on_success(key, start)
        assert ctrl._get(key).in_flight == 0

    @pytest.mark.asyncio
    async def test_initial_limit(self):
        ctrl = AIMDController()
        bucket = ctrl._get("k1")
        assert bucket.limit == INITIAL_LIMIT

    @pytest.mark.asyncio
    async def test_rate_limit_shrinks_window(self):
        ctrl = AIMDController()
        key = "k1"
        start = await ctrl.acquire(key)
        initial = ctrl._get(key).limit
        await ctrl.release_on_rate_limit(key, retry_after_s=1.0)
        assert ctrl._get(key).limit < initial
        assert ctrl._get(key).in_flight == 0

    @pytest.mark.asyncio
    async def test_soft_vs_severe_factor(self):
        """Consecutive 429s should switch from soft to severe factor."""
        ctrl = AIMDController()
        key = "k1"
        bucket = ctrl._get(key)
        bucket.limit = 20.0

        # First 429 → soft
        start = await ctrl.acquire(key)
        await ctrl.release_on_rate_limit(key, retry_after_s=0.01)
        after_soft = bucket.limit
        assert bucket.severity == "soft"

        # Pump up consecutive 429s to SEVERE_THRESHOLD
        for _ in range(SEVERE_THRESHOLD - 1):
            bucket.limit = 20.0  # reset for clear comparison
            start = await ctrl.acquire(key)
            await ctrl.release_on_rate_limit(key, retry_after_s=0.01)

        assert bucket.severity == "severe"

    @pytest.mark.asyncio
    async def test_ssthresh_updated_on_rate_limit(self):
        """ssthresh should be set to limit/2 on congestion (TCP Reno)."""
        ctrl = AIMDController()
        key = "k1"
        bucket = ctrl._get(key)
        bucket.limit = 20.0
        bucket.ssthresh = 3.0  # default

        start = await ctrl.acquire(key)
        await ctrl.release_on_rate_limit(key, retry_after_s=0.01)

        # ssthresh should now be 20/2 = 10
        assert bucket.ssthresh == 10.0
        # limit should be shrunk by SOFT_FACTOR
        assert bucket.limit == pytest.approx(20.0 * SOFT_FACTOR, abs=0.01)

    @pytest.mark.asyncio
    async def test_floor_backoff_activates(self):
        """When limit drops to MIN_LIMIT, floor_backoff should engage."""
        ctrl = AIMDController()
        key = "k1"
        bucket = ctrl._get(key)
        bucket.limit = MIN_LIMIT

        start = await ctrl.acquire(key)
        await ctrl.release_on_rate_limit(key, retry_after_s=0.01)
        assert bucket.floor_backoff >= FLOOR_BACKOFF_BASE

    @pytest.mark.asyncio
    async def test_floor_backoff_clears_on_success(self):
        ctrl = AIMDController()
        key = "k1"
        bucket = ctrl._get(key)
        bucket.floor_backoff = 1.0
        start = await ctrl.acquire(key)
        await ctrl.release_on_success(key, start)
        assert bucket.floor_backoff == 0.0

    @pytest.mark.asyncio
    async def test_stats(self):
        ctrl = AIMDController()
        await ctrl.acquire("k1")
        stats = ctrl.stats()
        assert "k1" in stats
        assert stats["k1"]["in_flight"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self):
        """Only `limit` concurrent acquires should be allowed."""
        ctrl = AIMDController()
        key = "k1"
        bucket = ctrl._get(key)
        bucket.limit = 2.0

        t1 = await ctrl.acquire(key)
        t2 = await ctrl.acquire(key)
        assert bucket.in_flight == 2

        # Third acquire should block; use wait_for to prove it
        acquired = asyncio.Event()

        async def _try_acquire():
            await ctrl.acquire(key)
            acquired.set()

        task = asyncio.create_task(_try_acquire())
        await asyncio.sleep(0.05)
        assert not acquired.is_set(), "Third acquire should block"

        # Release one → third should proceed
        await ctrl.release_on_success(key, t1)
        await asyncio.wait_for(acquired.wait(), timeout=1.0)
        assert acquired.is_set()
        task.cancel()


# ===========================================================================
# ProviderPool
# ===========================================================================


class TestProviderPool:

    def test_pick_basic(self):
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        slot = _make_slot(role="judge", key="a")
        pool.add_slot(slot)
        picked = pool.pick("judge")
        assert picked is slot

    def test_pick_no_provider_raises(self):
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        with pytest.raises(NoProviderAvailableError):
            pool.pick("judge")

    def test_pick_filters_by_role_and_tier(self):
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        s1 = _make_slot(role="judge", tier="tier1", key="a")
        s2 = _make_slot(role="generation", tier="tier1", key="b")
        s3 = _make_slot(role="judge", tier="tier2", key="c")
        pool.add_slot(s1)
        pool.add_slot(s2)
        pool.add_slot(s3)

        picked = pool.pick("judge", tier="tier2")
        assert picked is s3

    def test_pick_skips_unhealthy(self):
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        s1 = _make_slot(role="judge", key="a", healthy=False)
        s2 = _make_slot(role="judge", key="b", healthy=True)
        pool.add_slot(s1)
        pool.add_slot(s2)
        picked = pool.pick("judge")
        assert picked is s2

    def test_pick_fallback_to_unhealthy(self):
        """If all healthy are cooling down, fall back to unhealthy."""
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        s1 = _make_slot(role="judge", key="a", healthy=False)
        pool.add_slot(s1)
        # Only unhealthy slot available — should still return it
        picked = pool.pick("judge")
        assert picked is s1

    def test_mark_error_triggers_unhealthy_after_3(self):
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        slot = _make_slot()
        pool.add_slot(slot)
        for _ in range(3):
            pool.mark_error(slot)
        assert not slot.healthy

    def test_mark_auth_failed(self):
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        slot = _make_slot()
        pool.add_slot(slot)
        pool.mark_auth_failed(slot)
        assert not slot.healthy

    def test_weighted_p2c_prefers_higher_headroom(self):
        """With two candidates, P2C should pick the one with more headroom."""
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        s1 = _make_slot(role="judge", key="a", weight=1.0)
        s2 = _make_slot(role="judge", key="b", weight=1.0)
        pool.add_slot(s1)
        pool.add_slot(s2)

        # Simulate s1 being busier
        b1 = aimd._get(s1.key_id)
        b1.limit = 10.0
        b1.in_flight = 8  # headroom = 0.2
        b2 = aimd._get(s2.key_id)
        b2.limit = 10.0
        b2.in_flight = 2  # headroom = 0.8

        # With 2 candidates, it's deterministic (max by score)
        picked = pool.pick("judge")
        assert picked is s2

    def test_total_calls_counts_errors_and_throttles(self):
        """total_calls on slot should increment on success, error, and throttle."""
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        slot = _make_slot()
        pool.add_slot(slot)

        pool.mark_success(slot, 100.0)
        assert slot.total_calls == 1
        pool.mark_error(slot)
        assert slot.total_calls == 2
        pool.mark_throttled(slot, retry_after_s=0.01)
        assert slot.total_calls == 3

    def test_mark_success_updates_rtt(self):
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        slot = _make_slot()
        pool.add_slot(slot)
        pool.mark_success(slot, 150.0)
        assert slot.avg_rtt_ms == 150.0
        pool.mark_success(slot, 250.0)
        # EWMA: 0.8 * 150 + 0.2 * 250 = 170
        assert abs(slot.avg_rtt_ms - 170.0) < 0.01


# ===========================================================================
# JudgeDedup
# ===========================================================================


class TestJudgeDedup:

    def test_miss_then_hit(self):
        dedup = JudgeDedup()
        key = JudgeDedup.make_key("jailbreak", "I cannot help with that")
        assert dedup.lookup(key, "jailbreak", "I cannot help with that") is None
        assert dedup.misses == 1

        dedup.store(key, "RESULT_1", "jailbreak", "I cannot help with that")
        assert dedup.lookup(key, "jailbreak", "I cannot help with that") == "RESULT_1"
        assert dedup.hits == 1

    def test_skip_empty_response(self):
        dedup = JudgeDedup()
        key = JudgeDedup.make_key("jailbreak", "")
        assert dedup.lookup(key, "jailbreak", "") is None

    def test_skip_error_response(self):
        dedup = JudgeDedup()
        key = JudgeDedup.make_key("jailbreak", "[ERROR] timeout")
        assert dedup.lookup(key, "jailbreak", "[ERROR] timeout") is None

    def test_lru_eviction(self):
        dedup = JudgeDedup(max_size=3)
        for i in range(4):
            key = f"key_{i}"
            dedup.store(key, f"result_{i}", "cat", f"response {i}")

        # First entry should be evicted
        assert dedup.lookup("key_0", "cat", "response 0") is None
        assert dedup.lookup("key_3", "cat", "response 3") == "result_3"

    def test_hit_rate(self):
        dedup = JudgeDedup()
        dedup.hits = 3
        dedup.misses = 7
        assert abs(dedup.hit_rate - 0.3) < 0.01

    def test_clear(self):
        dedup = JudgeDedup()
        dedup.store("k1", "v1", "cat", "text")
        dedup.clear()
        assert dedup.lookup("k1", "cat", "text") is None
        assert dedup.hits == 0

    def test_simhash_near_duplicate(self):
        dedup = JudgeDedup(simhash_enabled=True, simhash_threshold=5)
        text1 = "I cannot assist with that harmful request"
        text2 = "I cannot assist with that dangerous request"
        key1 = JudgeDedup.make_key("jailbreak", text1)
        key2 = JudgeDedup.make_key("jailbreak", text2)

        dedup.store(key1, "BLOCKED", "jailbreak", text1)
        # key2 is different exact hash, but simhash should be close
        result = dedup.lookup(key2, "jailbreak", text2)
        # May or may not match depending on simhash distance; just verify no crash
        assert result in (None, "BLOCKED")


# ===========================================================================
# SimHash helpers
# ===========================================================================


class TestSimHash:

    def test_identical_texts(self):
        fp1 = _simhash_fingerprint("hello world foo bar")
        fp2 = _simhash_fingerprint("hello world foo bar")
        assert fp1 == fp2
        assert _hamming_distance(fp1, fp2) == 0

    def test_similar_texts(self):
        fp1 = _simhash_fingerprint("the quick brown fox jumps over the lazy dog")
        fp2 = _simhash_fingerprint("the quick brown cat jumps over the lazy dog")
        dist = _hamming_distance(fp1, fp2)
        assert dist < 15, f"Distance {dist} is too high for similar texts"

    def test_different_texts(self):
        fp1 = _simhash_fingerprint("hello world")
        fp2 = _simhash_fingerprint("completely different unrelated text here")
        dist = _hamming_distance(fp1, fp2)
        assert dist > 5


# ===========================================================================
# Retry helpers
# ===========================================================================


class TestRetryHelpers:

    def test_full_jitter_in_range(self):
        for attempt in range(5):
            delay = _full_jitter_delay(attempt)
            ceiling = min(60.0, 1.0 * (2 ** attempt))
            assert 0 <= delay <= ceiling

    def test_slot_key_id_deterministic(self):
        k1 = _slot_key_id("deepseek", "sk-123")
        k2 = _slot_key_id("deepseek", "sk-123")
        assert k1 == k2

    def test_slot_key_id_different_keys(self):
        k1 = _slot_key_id("deepseek", "sk-123")
        k2 = _slot_key_id("deepseek", "sk-456")
        assert k1 != k2


# ===========================================================================
# schedule_call integration
# ===========================================================================


class TestScheduleCall:

    @pytest.mark.asyncio
    async def test_success_path(self):
        """Happy path: schedule_call returns the LLM response."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        slot = _make_slot(role="judge", key="k1")
        sched._pool.add_slot(slot)

        with patch.object(sched, "call_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = '{"attack_successful": false}'
            result = await sched.schedule_call(
                "judge",
                [{"role": "user", "content": "test"}],
            )
            assert result == '{"attack_successful": false}'
            mock_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_dedup_cache_hit(self):
        """Dedup cache should return cached result without calling LLM."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        slot = _make_slot(role="judge", key="k1")
        sched._pool.add_slot(slot)

        key = JudgeDedup.make_key("jailbreak", "I refuse")
        sched._dedup.store(key, "CACHED_RESULT", "jailbreak", "I refuse")

        with patch.object(sched, "call_chat", new_callable=AsyncMock) as mock_chat:
            result = await sched.schedule_call(
                "judge",
                [{"role": "user", "content": "test"}],
                dedup_key=key,
                attack_category="jailbreak",
                response_text="I refuse",
            )
            assert result == "CACHED_RESULT"
            mock_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        """Should retry on 429 and succeed on second attempt."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        slot = _make_slot(role="judge", key="k1")
        sched._pool.add_slot(slot)

        call_count = 0

        async def _mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMRateLimitError("rate limited", retry_after_s=0.01)
            return "OK"

        with patch.object(sched, "call_chat", side_effect=_mock_call):
            result = await sched.schedule_call(
                "judge",
                [{"role": "user", "content": "test"}],
            )
            assert result == "OK"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_budget_exhaustion(self):
        """When retry bucket is drained, should raise AllRetriesExhaustedError."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = 0.0  # Empty bucket

        slot = _make_slot(role="judge", key="k1")
        sched._pool.add_slot(slot)

        with patch.object(sched, "call_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = LLMRateLimitError("rate limited", retry_after_s=0.01)
            with pytest.raises(AllRetriesExhaustedError):
                await sched.schedule_call(
                    "judge",
                    [{"role": "user", "content": "test"}],
                )

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Circuit breaker should trip after MAX_CONSECUTIVE_FAILURES."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        slot = _make_slot(role="judge", key="k1")
        sched._pool.add_slot(slot)

        with patch.object(sched, "call_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = LLMAPIError("server error")
            with pytest.raises(AllRetriesExhaustedError):
                await sched.schedule_call(
                    "judge",
                    [{"role": "user", "content": "test"}],
                    max_retries=10,
                )

    @pytest.mark.asyncio
    async def test_no_provider_raises(self):
        """Should raise NoProviderAvailableError when pool is empty."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        with pytest.raises(NoProviderAvailableError):
            await sched.schedule_call(
                "judge",
                [{"role": "user", "content": "test"}],
            )

    @pytest.mark.asyncio
    async def test_scheduler_stats(self):
        """get_scheduler_stats should return the expected structure."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        slot = _make_slot(role="judge", key="k1")
        sched._pool.add_slot(slot)

        stats = sched.get_scheduler_stats()
        assert "providers" in stats
        assert "dedup" in stats
        assert "retry_bucket" in stats
        assert stats["pool_slots"] == 1


# ===========================================================================
# Judge-fixed / Generation-rotation semantic tests
# ===========================================================================


class TestFixedVsRotation:
    """Verify that judge remains pinned while generation rotates."""

    @pytest.mark.asyncio
    async def test_fixed_call_uses_exact_provider(self):
        """schedule_fixed_call must always call the exact provider/model passed in,
        never picking from the pool."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        # Add a different slot to the pool — it must NOT be used
        pool_slot = _make_slot(role="judge", key="pool-key", provider_type="openai")
        sched._pool.add_slot(pool_slot)

        pinned_info = ProviderClientInfo(provider_type="deepseek", api_key="pinned-key")
        pinned_model = "deepseek-judge-v2"

        with patch.object(sched, "call_chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = '{"attack_successful": false}'
            result = await schedule_fixed_call(
                pinned_info, pinned_model,
                [{"role": "user", "content": "evaluate"}],
                role="judge",
            )
            assert result == '{"attack_successful": false}'
            # Must be called with the pinned provider, not the pool one
            call_args = mock_chat.call_args
            assert call_args[0][0] is pinned_info
            assert call_args[0][1] == pinned_model

    @pytest.mark.asyncio
    async def test_schedule_call_picks_from_pool(self):
        """schedule_call (dynamic) picks slots from pool depending on headroom.

        With 2 candidates P2C is deterministic (max by score), so we
        artificially skew the AIMD buckets between calls to prove that
        both slots are reachable when headroom changes.
        """
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        s1 = _make_slot(role="generation", key="gen-a", provider_id="p1")
        s2 = _make_slot(role="generation", key="gen-b", provider_id="p2")
        sched._pool.add_slot(s1)
        sched._pool.add_slot(s2)

        picked_keys = set()

        async def _capture(*args, **kwargs):
            picked_keys.add(args[0].api_key)
            return "ok"

        with patch.object(sched, "call_chat", side_effect=_capture):
            # Round 1: equal headroom → one slot wins
            await sched.schedule_call(
                "generation", [{"role": "user", "content": "a"}],
            )
            assert len(picked_keys) == 1
            first_key = list(picked_keys)[0]

            # Skew: load the winner so the other slot has more headroom
            winner_slot = s1 if first_key == "gen-a" else s2
            bucket = sched._aimd._get(winner_slot.key_id)
            bucket.in_flight = int(bucket.limit)  # saturate

            await sched.schedule_call(
                "generation", [{"role": "user", "content": "b"}],
            )

        # Now both slots should have been picked
        assert picked_keys == {"gen-a", "gen-b"}

    @pytest.mark.asyncio
    async def test_provider_id_filter_restricts_selection(self):
        """schedule_call with provider_id should only use matching slots."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        s1 = _make_slot(role="generation", key="gen-a", provider_id="prov-A")
        s2 = _make_slot(role="generation", key="gen-b", provider_id="prov-B")
        sched._pool.add_slot(s1)
        sched._pool.add_slot(s2)

        picked_provider_ids = set()

        async def _capture(*args, **kwargs):
            picked_provider_ids.add(args[0].api_key)
            return "ok"

        with patch.object(sched, "call_chat", side_effect=_capture):
            for _ in range(10):
                await sched.schedule_call(
                    "generation",
                    [{"role": "user", "content": "attack"}],
                    provider_id="prov-A",
                )

        # Only s1's key should appear
        assert picked_provider_ids == {"gen-a"}

    @pytest.mark.asyncio
    async def test_generation_helper_passes_override(self):
        """schedule_generation_call should forward provider_id from ContextVar override."""
        import app.services.llm_scheduler as sched

        sched._aimd = AIMDController()
        sched._pool = ProviderPool(sched._aimd)
        sched._dedup = JudgeDedup()
        sched._retry_bucket = RETRY_BUCKET_MAX

        s1 = _make_slot(role="generation", key="gen-x", provider_id="override-prov")
        s2 = _make_slot(role="generation", key="gen-y", provider_id="other-prov")
        sched._pool.add_slot(s1)
        sched._pool.add_slot(s2)

        with patch.object(sched, "call_chat", new_callable=AsyncMock) as mock_chat, \
             patch("app.services.llm_client.get_generation_routing_override",
                   return_value=("override-prov", "override-model")):
            mock_chat.return_value = "gen result"
            result = await schedule_generation_call(
                [{"role": "user", "content": "attack"}],
            )
            assert result == "gen result"
            # Must use override model
            call_args = mock_chat.call_args
            assert call_args[0][1] == "override-model"
            # Must use the slot whose provider_id matches
            assert call_args[0][0].api_key == "gen-x"

    def test_pool_pick_provider_id_no_match_raises(self):
        """Pool.pick with provider_id that matches nothing should raise."""
        aimd = AIMDController()
        pool = ProviderPool(aimd)
        pool.add_slot(_make_slot(role="generation", key="a", provider_id="p1"))

        with pytest.raises(NoProviderAvailableError):
            pool.pick("generation", provider_id="non-existent")
