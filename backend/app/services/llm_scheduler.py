"""LLM Scheduling Layer — adaptive concurrency, multi-key routing, judge dedup.

Sits between callers (ai_analyzer, scan_runner, engines) and llm_client.call_chat().
Provides: AIMD concurrency control, weighted P2C provider selection, judge result
deduplication, full-jitter retry with token-bucket throttling.

Design doc: docs/dev-notes/llm-scheduler-design.md
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.latency_tracker import record_latency
from app.services.llm_client import (
    LLMAPIError,
    LLMRateLimitError,
    ProviderClientInfo,
    call_chat,
    make_platform_provider,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants — AIMD
# ============================================================================

INITIAL_LIMIT = 5.0
SSTHRESH = 3.0
MAX_LIMIT = 50.0
MIN_LIMIT = 1.0

SOFT_FACTOR = 0.7
SEVERE_FACTOR = 0.5
SEVERE_THRESHOLD = 3

INCREMENT = 1.0
UTILIZATION_GATE = 0.5
PROBE_INTERVAL_S = 5.0

SLOW_RTT_TIMEOUT_S = 30.0

FLOOR_BACKOFF_BASE = 0.1
FLOOR_BACKOFF_MAX = 2.0
FLOOR_BACKOFF_MULT = 2.0

DEFAULT_COOLDOWN_S = 1.0
SEVERITY_DECAY_S = 5.0

QUOTA_LOW_THRESHOLD = 0.10
QUOTA_PREEMPT_RATIO = 0.80

# ============================================================================
# Constants — Retry
# ============================================================================

RETRY_BASE_S = 1.0
RETRY_CAP_S = 60.0
MAX_RETRIES = 3

RETRY_BUCKET_MAX = 10.0
RETRY_BUCKET_REFILL = 0.5
RETRY_COST_429 = 5.0
RETRY_COST_5XX = 1.0

MAX_CONSECUTIVE_FAILURES = 3

# ============================================================================
# Constants — JudgeDedup
# ============================================================================

DEDUP_CACHE_MAX = 1000
SIMHASH_ENABLED = False
SIMHASH_THRESHOLD = 3

# ============================================================================
# Exceptions
# ============================================================================


class NoProviderAvailableError(Exception):
    """All provider slots are unhealthy or cooling down."""


class AllRetriesExhaustedError(Exception):
    """Every retry attempt failed."""


# ============================================================================
# AIMDController — per provider-key adaptive concurrency
# ============================================================================


@dataclass
class _AIMDBucket:
    """Mutable concurrency state for one (provider_type, api_key) pair."""

    limit: float = INITIAL_LIMIT
    ssthresh: float = SSTHRESH
    in_flight: int = 0
    cooldown_until: float = 0.0
    consecutive_429: int = 0
    severity: str = "healthy"         # healthy | soft | severe
    floor_backoff: float = 0.0
    last_429_at: float = 0.0
    total_calls: int = 0
    total_429: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _gate: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def __post_init__(self) -> None:
        self._gate.set()


class AIMDController:
    """Manages one _AIMDBucket per provider-key string."""

    def __init__(self) -> None:
        self._buckets: dict[str, _AIMDBucket] = {}

    def _get(self, key: str) -> _AIMDBucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _AIMDBucket()
            self._buckets[key] = bucket
        return bucket

    # -- public stats -------------------------------------------------------

    def stats(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for key, b in self._buckets.items():
            out[key] = {
                "limit": round(b.limit, 2),
                "in_flight": b.in_flight,
                "total_calls": b.total_calls,
                "total_429": b.total_429,
                "severity": b.severity,
            }
        return out

    # -- acquire / release --------------------------------------------------

    async def acquire(self, key: str) -> float:
        """Wait until a slot is available, then claim it.

        Returns the monotonic timestamp (start_time) for RTT measurement.
        """
        bucket = self._get(key)

        # --- cooldown & floor backoff (outside context-manager to avoid
        #     cancel-safety issues with manual release/reacquire) ----------
        await bucket._lock.acquire()
        try:
            now = time.monotonic()
            cooldown_delay = max(0.0, bucket.cooldown_until - now)
            floor_delay = (
                bucket.floor_backoff
                if bucket.limit <= MIN_LIMIT and bucket.floor_backoff > 0
                else 0.0
            )
        finally:
            bucket._lock.release()

        if cooldown_delay > 0:
            await asyncio.sleep(cooldown_delay)
        if floor_delay > 0:
            await asyncio.sleep(floor_delay)

        # --- wait for in_flight < limit (no lock held while sleeping) -----
        while True:
            async with bucket._lock:
                if bucket.in_flight < int(bucket.limit):
                    bucket.in_flight += 1
                    bucket.total_calls += 1
                    return time.monotonic()
                bucket._gate.clear()
            # Wait outside lock for a signal
            await bucket._gate.wait()

    async def release_on_success(
        self,
        key: str,
        start_time: float,
        rate_limit_headers: dict[str, str] | None = None,
    ) -> None:
        """Signal a successful call. Adjusts concurrency window upward."""
        bucket = self._get(key)
        rtt = time.monotonic() - start_time

        # Feed the global latency estimate so attack-engine timeouts can adapt
        # to the target/relay model's real speed (see engine_utils.scaled_timeout).
        record_latency(rtt)

        async with bucket._lock:
            bucket.in_flight -= 1
            bucket.floor_backoff = 0.0
            bucket.consecutive_429 = 0

            # Severity decay
            if bucket.severity != "healthy":
                if (time.monotonic() - bucket.last_429_at) > SEVERITY_DECAY_S:
                    bucket.severity = (
                        "healthy" if bucket.severity == "soft" else "soft"
                    )

            # Promptfoo: preemptive reduction from rate-limit headers
            if rate_limit_headers:
                remaining = _safe_float(rate_limit_headers.get(
                    "x-ratelimit-remaining-requests"
                ))
                total = _safe_float(rate_limit_headers.get(
                    "x-ratelimit-limit-requests"
                ))
                if total and total > 0 and remaining is not None:
                    if remaining / total < QUOTA_LOW_THRESHOLD:
                        bucket.limit = max(
                            bucket.limit * QUOTA_PREEMPT_RATIO, MIN_LIMIT
                        )
                        bucket._gate.set()
                        return

            # Netflix: RTT timeout = implicit drop
            if rtt > SLOW_RTT_TIMEOUT_S:
                bucket.limit = max(bucket.limit * SOFT_FACTOR, MIN_LIMIT)
                bucket._gate.set()
                return

            # Netflix: utilization gate — only increase if busy enough
            if bucket.in_flight < bucket.limit * UTILIZATION_GATE:
                bucket._gate.set()
                return

            # Two-phase growth
            now = time.monotonic()
            if (now - bucket.last_429_at) > PROBE_INTERVAL_S:
                if bucket.limit < bucket.ssthresh:
                    # Slow start: exponential
                    bucket.limit = min(bucket.limit * 2, MAX_LIMIT)
                else:
                    # Congestion avoidance: linear
                    bucket.limit = min(bucket.limit + INCREMENT, MAX_LIMIT)

            bucket._gate.set()

    async def release_on_rate_limit(
        self,
        key: str,
        retry_after_s: float | None = None,
    ) -> None:
        """Signal a 429. Shrink window, apply cooldown."""
        bucket = self._get(key)

        async with bucket._lock:
            bucket.in_flight -= 1
            bucket.consecutive_429 += 1
            bucket.last_429_at = time.monotonic()
            bucket.total_429 += 1

            # TCP Reno: update ssthresh before shrinking
            bucket.ssthresh = max(bucket.limit / 2, MIN_LIMIT)

            # Dual-severity multiplicative decrease
            if bucket.consecutive_429 >= SEVERE_THRESHOLD:
                bucket.severity = "severe"
                factor = SEVERE_FACTOR
            else:
                bucket.severity = "soft"
                factor = SOFT_FACTOR

            bucket.limit = max(bucket.limit * factor, MIN_LIMIT)

            # Floor backoff (Camunda)
            if bucket.limit <= MIN_LIMIT:
                if bucket.floor_backoff <= 0:
                    bucket.floor_backoff = FLOOR_BACKOFF_BASE
                else:
                    bucket.floor_backoff = min(
                        bucket.floor_backoff * FLOOR_BACKOFF_MULT,
                        FLOOR_BACKOFF_MAX,
                    )

            cooldown = retry_after_s if (retry_after_s and retry_after_s > 0) else DEFAULT_COOLDOWN_S
            bucket.cooldown_until = time.monotonic() + cooldown

            bucket._gate.set()

    async def release_on_error(self, key: str) -> None:
        """Signal a non-429 API error. Just release the slot."""
        bucket = self._get(key)
        async with bucket._lock:
            bucket.in_flight -= 1
            bucket._gate.set()


# ============================================================================
# ProviderSlot + ProviderPool
# ============================================================================


@dataclass
class ProviderSlot:
    """One (provider, key, model, role) routing target."""

    provider_info: ProviderClientInfo
    model: str
    key_id: str               # hash(provider_type + api_key)
    role: str                 # "judge" | "generation"
    provider_id: str | None = None
    tier: str = "tier1"
    # --- health ---
    healthy: bool = True
    error_count: int = 0
    last_error_at: float = 0.0
    cooldown_until: float = 0.0
    # --- load balancing ---
    weight: float = 1.0
    success_count: int = 0
    total_calls: int = 0
    avg_rtt_ms: float = 0.0


def _slot_key_id(provider_type: str, api_key: str) -> str:
    """Deterministic short ID for a (provider_type, api_key) pair."""
    raw = f"{provider_type}:{api_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


class ProviderPool:
    """Manages a pool of ProviderSlots with health tracking and P2C selection."""

    def __init__(self, aimd: AIMDController) -> None:
        self._slots: list[ProviderSlot] = []
        self._aimd = aimd

    @property
    def slots(self) -> list[ProviderSlot]:
        return list(self._slots)

    def add_slot(self, slot: ProviderSlot) -> None:
        self._slots.append(slot)

    def clear(self) -> None:
        self._slots.clear()

    # -- selection -----------------------------------------------------------

    def pick(
        self,
        role: str,
        tier: str | None = None,
        provider_id: str | None = None,
    ) -> ProviderSlot:
        """Select the best healthy slot using Weighted P2C + AIMD headroom."""
        now = time.monotonic()

        candidates = [
            s for s in self._slots
            if s.role == role
            and (provider_id is None or s.provider_id == provider_id)
            and s.healthy
            and (tier is None or s.tier == tier)
            and now > s.cooldown_until
        ]

        if not candidates:
            # Fallback: ignore health/cooldown, keep role filter
            candidates = [
                s for s in self._slots
                if s.role == role and (provider_id is None or s.provider_id == provider_id)
            ]
            if not candidates:
                raise NoProviderAvailableError(
                    f"No provider available for role={role}, tier={tier}, provider_id={provider_id}"
                )

        return self._weighted_p2c(candidates)

    def _weighted_p2c(self, candidates: list[ProviderSlot]) -> ProviderSlot:
        if len(candidates) == 1:
            return candidates[0]

        if len(candidates) == 2:
            return max(candidates, key=self._score)

        a, b = random.sample(candidates, 2)
        return a if self._score(a) >= self._score(b) else b

    def _score(self, slot: ProviderSlot) -> float:
        bucket = self._aimd._get(slot.key_id)
        headroom = (bucket.limit - bucket.in_flight) / max(bucket.limit, 1.0)
        return headroom * slot.weight

    # -- health updates ------------------------------------------------------

    def mark_throttled(self, slot: ProviderSlot, retry_after_s: float | None = None) -> None:
        cooldown = retry_after_s if (retry_after_s and retry_after_s > 0) else DEFAULT_COOLDOWN_S
        slot.cooldown_until = time.monotonic() + cooldown
        slot.total_calls += 1

    def mark_error(self, slot: ProviderSlot) -> None:
        now = time.monotonic()
        # Reset error_count if last error was >60s ago
        if now - slot.last_error_at > 60:
            slot.error_count = 0
        slot.error_count += 1
        slot.total_calls += 1
        slot.last_error_at = now
        if slot.error_count >= 3:
            slot.healthy = False
            slot.cooldown_until = now + 60  # 60s probe window

    def mark_auth_failed(self, slot: ProviderSlot) -> None:
        slot.healthy = False

    def mark_success(self, slot: ProviderSlot, rtt_ms: float) -> None:
        slot.success_count += 1
        slot.total_calls += 1
        # EWMA RTT (alpha=0.2)
        if slot.avg_rtt_ms <= 0:
            slot.avg_rtt_ms = rtt_ms
        else:
            slot.avg_rtt_ms = 0.8 * slot.avg_rtt_ms + 0.2 * rtt_ms

    # -- pool initialization from DB -----------------------------------------

    async def load_from_db(self) -> None:
        """Read enabled providers from DB and populate slots."""
        try:
            from sqlalchemy import select
            from app.database import async_session
            from app.models.model_provider import ModelProvider, extract_raw_keys
            from app.services.llm_client import resolve_provider_model

            async with async_session() as db:
                rows = await db.execute(
                    select(ModelProvider).where(ModelProvider.enabled == True)  # noqa: E712
                )
                providers = rows.scalars().all()

            new_slots: list[ProviderSlot] = []
            for prov in providers:
                keys = extract_raw_keys(prov.api_key)
                if not keys:
                    continue
                for key in keys:
                    info = ProviderClientInfo(
                        provider_type=prov.provider_type,
                        api_key=key,
                        base_url=prov.base_url or None,
                    )
                    kid = _slot_key_id(prov.provider_type, key)

                    # Judge slot
                    if prov.is_judge_default or prov.judge_model:
                        try:
                            model = await resolve_provider_model(
                                provider_type=prov.provider_type,
                                api_key=key,
                                base_url=prov.base_url,
                                configured_models=[prov.judge_model, prov.mini_model],
                                role_label="judge",
                            )
                            new_slots.append(ProviderSlot(
                                provider_info=info, model=model,
                                key_id=kid, role="judge", provider_id=str(prov.id),
                            ))
                        except Exception:
                            logger.warning("Failed to resolve judge model for %s", kid)

                    # Generation slot
                    if prov.is_generation_default or prov.mini_model:
                        try:
                            model = await resolve_provider_model(
                                provider_type=prov.provider_type,
                                api_key=key,
                                base_url=prov.base_url,
                                configured_models=[prov.mini_model, prov.judge_model],
                                role_label="generation",
                            )
                            new_slots.append(ProviderSlot(
                                provider_info=info, model=model,
                                key_id=kid, role="generation", provider_id=str(prov.id),
                            ))
                        except Exception:
                            logger.warning("Failed to resolve gen model for %s", kid)

            self._slots = new_slots
            logger.info("ProviderPool loaded %d slots from DB", len(new_slots))
            if not new_slots:
                logger.warning(
                    "ProviderPool: 0 slots loaded — check that at least one "
                    "enabled provider with a valid API key exists in the DB"
                )
        except Exception:
            logger.exception("ProviderPool.load_from_db failed — pool will be empty")


# ============================================================================
# JudgeDedup — two-layer cache (normalized exact + optional SimHash)
# ============================================================================


class JudgeDedup:
    """Per-scan judge result cache to avoid redundant LLM calls."""

    def __init__(
        self,
        *,
        max_size: int = DEDUP_CACHE_MAX,
        simhash_enabled: bool = SIMHASH_ENABLED,
        simhash_threshold: int = SIMHASH_THRESHOLD,
    ) -> None:
        self._exact: OrderedDict[str, Any] = OrderedDict()
        self._simhash_index: dict[str, list[tuple[int, Any]]] = {}
        self._max_size = max_size
        self._simhash_enabled = simhash_enabled
        self._simhash_threshold = simhash_threshold
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "cache_size": len(self._exact),
        }

    @staticmethod
    def make_key(attack_category: str, response_text: str) -> str:
        normalized = response_text.strip()[:500]
        raw = f"{attack_category}:{normalized}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def lookup(self, key: str, attack_category: str = "", response_text: str = "") -> Any | None:
        """Return cached result or None. Layer 1: exact hash, Layer 2: SimHash."""
        # Skip caching for empty/error responses
        stripped = (response_text or "").strip()
        if not stripped or stripped.lower().startswith("[error]"):
            self.misses += 1
            return None

        # Layer 1: exact match
        if key in self._exact:
            self._exact.move_to_end(key)
            self.hits += 1
            return self._exact[key]

        # Layer 2: SimHash (optional)
        if self._simhash_enabled and attack_category:
            fp = _simhash_fingerprint(response_text)
            bucket = self._simhash_index.get(attack_category, [])
            for cached_fp, cached_result in bucket:
                if _hamming_distance(fp, cached_fp) <= self._simhash_threshold:
                    self.hits += 1
                    return cached_result

        self.misses += 1
        return None

    def store(self, key: str, result: Any, attack_category: str = "", response_text: str = "") -> None:
        """Store a judge result in both layers."""
        # LRU eviction
        if len(self._exact) >= self._max_size:
            self._exact.popitem(last=False)

        self._exact[key] = result

        if self._simhash_enabled and attack_category and response_text:
            fp = _simhash_fingerprint(response_text)
            self._simhash_index.setdefault(attack_category, []).append((fp, result))

    def clear(self) -> None:
        self._exact.clear()
        self._simhash_index.clear()
        self.hits = 0
        self.misses = 0


# -- SimHash helpers (lightweight, no external deps) -------------------------

def _simhash_fingerprint(text: str, bits: int = 64) -> int:
    """Compute a SimHash fingerprint for near-duplicate detection."""
    v = [0] * bits
    tokens = text.lower().split()
    for token in tokens:
        # md5 is used here purely as a fast non-cryptographic hash for
        # SimHash fingerprinting — no security properties needed.
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)  # noqa: S324
        for i in range(bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def _hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ============================================================================
# Retry helpers
# ============================================================================


def _full_jitter_delay(attempt: int) -> float:
    """AWS Full Jitter: sleep = random(0, min(cap, base × 2^attempt))"""
    ceiling = min(RETRY_CAP_S, RETRY_BASE_S * (2 ** attempt))
    return random.uniform(0, ceiling)


def _effective_delay(attempt: int, retry_after_s: float | None) -> float:
    """Retry-After header takes priority, with small jitter to avoid herd."""
    if retry_after_s is not None and retry_after_s > 0:
        return retry_after_s + random.uniform(0, min(1.0, retry_after_s * 0.1))
    return _full_jitter_delay(attempt)


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ============================================================================
# schedule_call — unified entry point
# ============================================================================


# Module-level singletons (initialized lazily via init_scheduler)
_aimd: AIMDController | None = None
_pool: ProviderPool | None = None
_dedup: JudgeDedup | None = None
_retry_bucket: float = RETRY_BUCKET_MAX


def _platform_slot(role: Literal["judge", "generation"]) -> ProviderSlot:
    from app.config import settings

    info = make_platform_provider()
    model = settings.openai_model if role == "judge" else settings.openai_mini_model
    return ProviderSlot(
        provider_info=info,
        model=model,
        key_id=_slot_key_id(info.provider_type, info.api_key),
        role=role,
        provider_id="platform",
    )


def _ensure_platform_fallback_slots() -> None:
    if _pool is None:
        return

    roles = {slot.role for slot in _pool.slots}
    if "judge" not in roles:
        _pool.add_slot(_platform_slot("judge"))
    if "generation" not in roles:
        _pool.add_slot(_platform_slot("generation"))


async def init_scheduler() -> None:
    """Initialize the global scheduler singletons. Call once at app startup."""
    global _aimd, _pool, _dedup, _retry_bucket
    _aimd = AIMDController()
    _pool = ProviderPool(_aimd)
    _dedup = JudgeDedup()
    _retry_bucket = RETRY_BUCKET_MAX
    await _pool.load_from_db()
    _ensure_platform_fallback_slots()
    logger.info("LLM scheduler initialized with %d slots", len(_pool.slots))


async def reload_pool() -> None:
    """Re-read providers from DB (e.g. after settings change)."""
    if _pool is not None:
        await _pool.load_from_db()
        _ensure_platform_fallback_slots()


def reset_scan_state() -> None:
    """Clear per-scan ephemeral state (dedup cache, retry bucket)."""
    global _retry_bucket
    if _dedup is not None:
        _dedup.clear()
    _retry_bucket = RETRY_BUCKET_MAX


def get_scheduler_stats() -> dict:
    """Return observability snapshot for websocket push."""
    return {
        "providers": _aimd.stats() if _aimd else {},
        "pool_slots": len(_pool.slots) if _pool else 0,
        "dedup": _dedup.stats() if _dedup else {},
        "retry_bucket": round(_retry_bucket, 2),
    }


def _check_dedup(
    dedup_key: str | None,
    attack_category: str,
    response_text: str,
) -> Any | None:
    if dedup_key and _dedup is not None:
        cached = _dedup.lookup(dedup_key, attack_category, response_text)
        if cached is not None:
            logger.debug("JudgeDedup hit for key=%s...", dedup_key[:8])
            return cached
    return None


def _store_dedup(
    dedup_key: str | None,
    result: Any,
    attack_category: str,
    response_text: str,
) -> None:
    if dedup_key and _dedup is not None:
        _dedup.store(dedup_key, result, attack_category, response_text)


async def schedule_fixed_call(
    provider_info: ProviderClientInfo,
    model: str,
    messages: list[dict],
    *,
    role: Literal["judge", "generation", "target"] = "judge",
    max_retries: int = MAX_RETRIES,
    dedup_key: str | None = None,
    attack_category: str = "",
    response_text: str = "",
    temperature: float = 0.7,
    json_mode: bool = False,
    max_tokens: int = 1024,
    seed: int | None = None,
) -> str:
    global _retry_bucket

    if _aimd is None:
        raise RuntimeError("Scheduler not initialized — call init_scheduler() first")

    cached = _check_dedup(dedup_key, attack_category, response_text)
    if cached is not None:
        return cached

    key_id = _slot_key_id(provider_info.provider_type, provider_info.api_key)
    consecutive_failures = 0

    for attempt in range(max_retries):
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(
                "Circuit breaker tripped after %d consecutive failures for fixed %s call",
                consecutive_failures,
                role,
            )
            break

        start_time = await _aimd.acquire(key_id)

        try:
            result = await call_chat(
                provider_info,
                model,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
                seed=seed,
            )

            await _aimd.release_on_success(key_id, start_time)
            _retry_bucket = min(_retry_bucket + RETRY_BUCKET_REFILL, RETRY_BUCKET_MAX)
            _store_dedup(dedup_key, result, attack_category, response_text)
            return result

        except LLMRateLimitError as exc:
            consecutive_failures += 1
            await _aimd.release_on_rate_limit(key_id, exc.retry_after_s)

            if _retry_bucket < RETRY_COST_429:
                raise AllRetriesExhaustedError(
                    f"Retry budget exhausted after {attempt + 1} fixed {role} attempts (429)"
                ) from exc
            _retry_bucket -= RETRY_COST_429

            delay = _effective_delay(attempt, exc.retry_after_s)
            logger.info(
                "429 on fixed %s %s, retry %d/%d after %.1fs",
                role,
                key_id,
                attempt + 1,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)

        except LLMAPIError as exc:
            consecutive_failures += 1
            await _aimd.release_on_error(key_id)

            if _retry_bucket < RETRY_COST_5XX:
                raise AllRetriesExhaustedError(
                    f"Retry budget exhausted after {attempt + 1} fixed {role} attempts (API error)"
                ) from exc
            _retry_bucket -= RETRY_COST_5XX

            delay = _full_jitter_delay(attempt)
            logger.info(
                "API error on fixed %s %s, retry %d/%d after %.1fs",
                role,
                key_id,
                attempt + 1,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)

        except Exception:
            await _aimd.release_on_error(key_id)
            raise

    raise AllRetriesExhaustedError(
        f"All {max_retries} retries exhausted for fixed role={role}"
    )


async def schedule_generation_call(
    messages: list[dict],
    *,
    model: str | None = None,
    tier: str | None = None,
    max_retries: int = MAX_RETRIES,
    temperature: float = 0.7,
    json_mode: bool = False,
    max_tokens: int = 1024,
) -> str:
    from app.services.llm_client import get_generation_routing_override

    override_provider_id, override_model = get_generation_routing_override()
    return await schedule_call(
        "generation",
        messages,
        model=model or override_model,
        tier=tier,
        provider_id=override_provider_id,
        max_retries=max_retries,
        temperature=temperature,
        json_mode=json_mode,
        max_tokens=max_tokens,
    )


async def schedule_call(
    role: Literal["judge", "generation"],
    messages: list[dict],
    model: str | None = None,
    *,
    tier: str | None = None,
    provider_id: str | None = None,
    max_retries: int = MAX_RETRIES,
    dedup_key: str | None = None,
    attack_category: str = "",
    response_text: str = "",
    temperature: float = 0.7,
    json_mode: bool = False,
    max_tokens: int = 1024,
) -> str:
    """Unified LLM call with dedup → P2C selection → AIMD → retry.

    Args:
        role: "judge" or "generation".
        messages: Standard OpenAI-style message list.
        model: Override model (uses slot default if None).
        tier: Restrict to specific tier.
        max_retries: Max retry attempts.
        dedup_key: Pre-computed dedup hash (JudgeDedup.make_key).
        attack_category: For SimHash grouping.
        response_text: Original target response (for dedup skip checks).
        temperature: Sampling temperature.
        json_mode: Request JSON-formatted output.
        max_tokens: Max response tokens.

    Returns:
        The LLM response text.

    Raises:
        NoProviderAvailableError: No healthy provider for the requested role.
        AllRetriesExhaustedError: All retries exhausted.
    """
    global _retry_bucket

    if _pool is None or _aimd is None:
        raise RuntimeError("Scheduler not initialized — call init_scheduler() first")

    cached = _check_dedup(dedup_key, attack_category, response_text)
    if cached is not None:
        return cached

    consecutive_failures = 0

    for attempt in range(max_retries):
        # Circuit breaker
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning("Circuit breaker tripped after %d consecutive failures", consecutive_failures)
            break

        try:
            slot = _pool.pick(role, tier, provider_id=provider_id)
        except NoProviderAvailableError:
            raise

        effective_model = model or slot.model
        start_time = await _aimd.acquire(slot.key_id)

        try:
            result = await call_chat(
                slot.provider_info,
                effective_model,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
            )

            rtt_ms = (time.monotonic() - start_time) * 1000
            await _aimd.release_on_success(slot.key_id, start_time)
            _pool.mark_success(slot, rtt_ms)

            # Refill retry bucket on success
            _retry_bucket = min(_retry_bucket + RETRY_BUCKET_REFILL, RETRY_BUCKET_MAX)

            _store_dedup(dedup_key, result, attack_category, response_text)

            return result

        except LLMRateLimitError as exc:
            consecutive_failures += 1
            await _aimd.release_on_rate_limit(slot.key_id, exc.retry_after_s)
            _pool.mark_throttled(slot, exc.retry_after_s)

            # Token bucket gate
            if _retry_bucket < RETRY_COST_429:
                logger.warning(
                    "Retry token bucket exhausted (%.1f < %.1f), giving up",
                    _retry_bucket, RETRY_COST_429,
                )
                raise AllRetriesExhaustedError(
                    f"Retry budget exhausted after {attempt + 1} attempts (429)"
                ) from exc
            _retry_bucket -= RETRY_COST_429

            delay = _effective_delay(attempt, exc.retry_after_s)
            logger.info(
                "429 on %s, retry %d/%d after %.1fs",
                slot.key_id, attempt + 1, max_retries, delay,
            )
            await asyncio.sleep(delay)

        except LLMAPIError as exc:
            consecutive_failures += 1
            await _aimd.release_on_error(slot.key_id)
            _pool.mark_error(slot)

            if _retry_bucket < RETRY_COST_5XX:
                logger.warning("Retry token bucket exhausted for API error")
                raise AllRetriesExhaustedError(
                    f"Retry budget exhausted after {attempt + 1} attempts (API error)"
                ) from exc
            _retry_bucket -= RETRY_COST_5XX

            delay = _full_jitter_delay(attempt)
            logger.info(
                "API error on %s, retry %d/%d after %.1fs",
                slot.key_id, attempt + 1, max_retries, delay,
            )
            await asyncio.sleep(delay)

        except Exception:
            await _aimd.release_on_error(slot.key_id)
            raise

    raise AllRetriesExhaustedError(
        f"All {max_retries} retries exhausted for role={role}"
    )
