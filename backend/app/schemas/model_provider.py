from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProviderType = Literal[
    "openai", "deepseek", "glm", "minimax", "gemini", "qwen", "claude",
    "nvidia", "mistral", "groq", "moonshot", "doubao", "yi",
    "baichuan", "stepfun", "siliconflow", "xai", "together",
    "custom",
]


# ---------------------------------------------------------------------------
# Structured API-key sub-models
# ---------------------------------------------------------------------------

class ApiKeyInfo(BaseModel):
    """Returned in the provider response — key is masked, never plaintext."""
    index: int
    label: str = ""
    masked_key: str


class ApiKeyInput(BaseModel):
    """Sent by the frontend when creating / editing a provider."""
    index: int = -1      # -1 → new key;  ≥ 0 → keep existing key at that index
    label: str = ""
    key: str = ""        # non-empty → new/replaced key;  empty → keep existing


# ---------------------------------------------------------------------------
# CRUD schemas
# ---------------------------------------------------------------------------

class ModelProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider_type: ProviderType = "custom"
    # Legacy single-key field (backward compat)
    api_key: str | None = None
    # Structured multi-key field (preferred)
    api_keys: list[ApiKeyInput] | None = None
    base_url: str | None = None
    judge_model: str | None = None
    mini_model: str | None = None
    enabled: bool = True


class ModelProviderUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    provider_type: ProviderType | None = None
    # Legacy single-key field
    api_key: str | None = None
    # Structured multi-key field (preferred — if present, overrides api_key)
    api_keys: list[ApiKeyInput] | None = None
    base_url: str | None = None
    judge_model: str | None = None
    mini_model: str | None = None
    enabled: bool | None = None


class ModelProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    # Never expose api_key — only indicate whether it is set
    api_key_set: bool
    api_key_count: int = 0
    api_keys: list[ApiKeyInfo] = []
    base_url: str | None
    judge_model: str | None
    mini_model: str | None
    is_judge_default: bool
    is_generation_default: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FetchModelsRequest(BaseModel):
    """Used by /fetch-models to retrieve available models without saving a provider.

    Either provide api_key directly, or provide provider_id to use the saved key.
    """
    api_key: str | None = None
    base_url: str | None = None
    provider_type: ProviderType = "custom"
    provider_id: str | None = None  # use saved API key if api_key is not provided
