from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
_ROOT_ENV = str(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    app_name: str = "Evidence-Ladder"
    debug: bool = False

    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o"
    openai_mini_model: str = "gpt-4o-mini"

    judge_version: str = "v1"

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        return str(v).rstrip("/")

    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> str:
        raw = str(v or "sqlite+aiosqlite:///./data/app.db").strip()
        for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
            if not raw.startswith(prefix):
                continue
            path_part = raw[len(prefix):]
            if path_part.startswith("./") or path_part.startswith("../"):
                path = (_BACKEND_ROOT / path_part).resolve()
                return f"{prefix}{path.as_posix()}"
        return raw

    cors_origins: list[str] = ["http://localhost:5173"]
    allow_localhost_targets: bool = True
    # Allow RFC1918 private IPs (Docker Compose internal networking).
    # Set ``ALLOW_PRIVATE_TARGETS=true`` when mock targets run in the
    # same compose project and are reached via service names that
    # resolve to 172.x.x.x addresses.
    allow_private_targets: bool = False

    # Stage 1.1a — Default-deny API authentication.
    # When True (default), every API request must carry X-API-Key matching
    # ``app_secret``; otherwise the request is rejected with 401. Public
    # paths (/health, /docs, /redoc, /openapi.json, OPTIONS preflight)
    # remain open. Set ``AUTH_REQUIRED=false`` for local development to
    # opt out, in which case ``app_secret`` is ignored.
    auth_required: bool = True
    app_secret: str = ""

    analyzer_concurrency: int = 12

    # ----- Verdict Arbiter rollout flags (Phase 4b) ----------------
    # Run the new evidence-based Arbiter alongside the legacy
    # ``classify_verdict`` and persist its result under
    # ``analysis_raw.arbiter_shadow`` for offline diff analysis. The
    # main pipeline still uses the legacy verdict — this is observation
    # only. Off by default to keep production behaviour identical.
    verdict_arbiter_shadow_mode: bool = False
    # Once shadow analysis confirms the new Arbiter is at least as good
    # as legacy, flip this to make it the source of truth. The legacy
    # verdict is still computed and recorded for diff (Phase 4b is
    # observable in both directions).
    verdict_arbiter_enabled: bool = False

    # How a judge abstention (``manual_review_needed``) scores when no stronger
    # evidence exists. A declared parameter of the measurement, not a tuning
    # knob: the same observations give different ASR under each value, so a
    # reported rate without it is not interpretable. Every assessment records
    # the value it was scored under.
    #   "e0"       -- undetermined, dropped from the denominator (default)
    #   "negative" -- counts as no evidence of success (behaviour before this
    #                 parameter existed; kept only for reproducing old runs)
    #   "e2"       -- counts as a weak judge-suspected positive
    abstention_policy: Literal["e0", "negative", "e2"] = "e0"

    # ----- Reproducible judging (opt-in; default keeps current behaviour) ----
    # When enabled, the LLM *judge* runs in a deterministic configuration for
    # reproducible measurement: temperature 0, best-effort provider ``seed``,
    # and the borderline second-pass confirmation is skipped (single pass).
    # Attack/generation/target calls are NOT affected — only evaluation.
    judge_deterministic: bool = False
    judge_seed: int = 20240617
    # Persist raw judge responses to disk and reuse them on identical inputs so
    # re-runs of the analysis stage reproduce byte-identical verdicts even when
    # the live model is non-deterministic. Off by default.
    judge_cache_enabled: bool = False
    judge_cache_dir: str = str(_BACKEND_ROOT / "data" / "judge_cache")

    # ----- Attack-engine call timeouts (default keeps current behaviour) ------
    # The multi-turn engines (crescendo/tap/pair/msj/fitd/ice/iris) cap each
    # attacker/judge LLM call with a short per-call timeout tuned for fast
    # models (~12s). Slow or reasoning-style target/relay models routinely
    # exceed that, which silently degrades multi-turn attacks (skipped turns,
    # empty branches) and biases ASR downward. This multiplier scales every
    # such timeout uniformly; 1.0 reproduces the original behaviour exactly.
    # It now acts as a manual *floor*/override on top of the adaptive sizing
    # below — leave it at 1.0 to let auto-scaling do the work.
    attack_timeout_multiplier: float = 1.0
    # When True (default), per-call timeouts auto-scale to the target/relay
    # model's observed round-trip latency: a fast model keeps the short
    # defaults, a slow/reasoning model gets proportionally more time. This
    # never *shortens* a timeout below its base, so fast models behave exactly
    # as before. Set False to use only the static multiplier above.
    attack_timeout_adaptive: bool = True
    # Latency (seconds) of a "fast" model that the hardcoded base timeouts were
    # tuned for. The adaptive factor is ``observed_latency / this``; observed
    # latencies at or below it produce no scaling (factor 1.0).
    attack_timeout_reference_latency_s: float = 4.0
    # Hard ceiling on the timeout growth factor (adaptive and manual combined),
    # so a single stuck/near-timeout call can never inflate timeouts without
    # bound. With base ~12s and factor 6.0 the longest per-call wait is ~72s.
    attack_timeout_max_factor: float = 6.0

    # Root .env loaded first; local backend/.env can override.
    # extra="ignore" so non-backend vars (e.g. TARGET_MODEL) don't cause errors.
    model_config = {
        "env_file": (_ROOT_ENV, ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
