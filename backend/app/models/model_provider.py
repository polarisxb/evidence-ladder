from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ---------------------------------------------------------------------------
# Structured API-key helpers
#
# The ``api_key`` column stores a JSON string of the form:
#     [{"label": "主力账号", "key": "sk-xxx"}, ...]
#
# Legacy data may still be plain-text (one key per line).  The helpers below
# handle both formats transparently.
# ---------------------------------------------------------------------------

def parse_api_keys(raw: str | None) -> list[dict[str, str]]:
    """Parse the ``api_key`` column into ``[{label, key}, ...]``."""
    if not raw or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [
                {"label": (item.get("label") or "").strip(), "key": item["key"].strip()}
                for item in parsed
                if isinstance(item, dict) and item.get("key", "").strip()
            ]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    # Legacy fallback: newline-separated plain keys
    return [{"label": "", "key": k.strip()} for k in raw.split("\n") if k.strip()]


def extract_raw_keys(raw: str | None) -> list[str]:
    """Return just the key strings (for scheduler / client use)."""
    return [e["key"] for e in parse_api_keys(raw)]


def first_api_key(raw: str | None) -> str:
    """Return the first non-empty key, or empty string."""
    keys = extract_raw_keys(raw)
    return keys[0] if keys else ""


def serialize_api_keys(entries: list[dict[str, str]]) -> str:
    """Serialize ``[{label, key}, ...]`` into a JSON string for DB storage."""
    clean = [
        {"label": (e.get("label") or "").strip(), "key": e["key"].strip()}
        for e in entries if e.get("key", "").strip()
    ]
    return json.dumps(clean, ensure_ascii=False)


def mask_key(key: str) -> str:
    """Return a masked representation: ``sk-...xxxx``."""
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:3]}...{key[-4:]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Provider base URLs — OpenAI-compatible unless noted otherwise
PROVIDER_TYPES = {
    "openai":      "https://api.openai.com/v1",
    "deepseek":    "https://api.deepseek.com",
    "glm":         "https://open.bigmodel.cn/api/paas/v4",
    "minimax":     "https://api.minimax.chat/v1",
    "gemini":      "https://generativelanguage.googleapis.com/v1beta/openai/",
    "qwen":        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    # Claude uses the Anthropic SDK, NOT the OpenAI-compatible path
    "claude":      "https://api.anthropic.com",
    # ── Additional well-known providers (all OpenAI-compatible) ──
    "nvidia":      "https://integrate.api.nvidia.com/v1",
    "mistral":     "https://api.mistral.ai/v1",
    "groq":        "https://api.groq.com/openai/v1",
    "moonshot":    "https://api.moonshot.cn/v1",
    "doubao":      "https://ark.cn-beijing.volces.com/api/v3",
    "yi":          "https://api.lingyiwanwu.com/v1",
    "baichuan":    "https://api.baichuan-ai.com/v1",
    "stepfun":     "https://api.stepfun.com/v1",
    "siliconflow": "https://api.siliconflow.com/v1",
    "xai":         "https://api.x.ai/v1",
    "together":    "https://api.together.xyz/v1",
    "custom":      "",
}


class ModelProvider(Base):
    """Stores AI provider configurations for judge and generation roles."""

    __tablename__ = "model_providers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False, default="custom")

    # Credentials — api_key is stored as-is; never returned in plaintext via API
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Selected models for each role
    judge_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mini_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # At most one provider per role is the global default (enforced in service layer)
    is_judge_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_generation_default: Mapped[bool] = mapped_column(Boolean, default=False)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
