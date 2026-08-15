"""Optional on-disk cache for raw LLM *judge* responses.

Enables byte-identical replay of the analysis stage: with
``settings.judge_cache_enabled`` on, an evaluation whose inputs (model,
temperature, seed, json_mode, messages, judge_version) have been seen before
reuses the stored raw response instead of calling the model again. This makes
reported numbers reproducible even though hosted LLMs are non-deterministic.

The cache is keyed by a content hash, so it is safe to share across runs and
machines. All failures degrade silently to a cache miss — it never blocks a
scan.
"""
import hashlib
import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def make_key(
    *,
    model: str,
    temperature: float,
    seed: int | None,
    json_mode: bool,
    messages: list[dict],
    judge_version: str,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "temperature": temperature,
            "seed": seed,
            "json_mode": json_mode,
            "messages": messages,
            "judge_version": judge_version,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_for(key: str) -> Path:
    return Path(settings.judge_cache_dir) / f"{key}.json"


def get(key: str) -> str | None:
    """Return the cached raw response for ``key``, or None on miss/disabled."""
    if not settings.judge_cache_enabled:
        return None
    path = _path_for(key)
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))["raw"]
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("judge cache read failed for %s: %s", key, exc)
    return None


def put(key: str, raw: str) -> None:
    """Persist the raw response for ``key`` (no-op when disabled)."""
    if not settings.judge_cache_enabled:
        return
    path = _path_for(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"raw": raw}, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("judge cache write failed for %s: %s", key, exc)
