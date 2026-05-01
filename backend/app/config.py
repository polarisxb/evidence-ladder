from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
_ROOT_ENV = str(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    app_name: str = "TianJian Libra"
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

    # Root .env loaded first; local backend/.env can override.
    # extra="ignore" so non-backend vars (e.g. TARGET_MODEL) don't cause errors.
    model_config = {
        "env_file": (_ROOT_ENV, ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
