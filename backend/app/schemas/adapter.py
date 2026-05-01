from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.adapter_renderer import validate_template_tree


def _ensure_template_paths(value: Any, field_name: str, *, allow_probe_context: bool = False) -> Any:
    validate_template_tree(
        value,
        field_name=field_name,
        allow_probe_context=allow_probe_context,
    )
    return value


class AdapterAuthConfig(BaseModel):
    type: Literal["none", "bearer", "header", "query"] = "none"
    secret_ref: str | None = None
    name: str | None = None
    scheme: str = "Bearer"

    @model_validator(mode="after")
    def validate_auth_requirements(self):
        if self.type == "none":
            return self
        if not (self.secret_ref or "").strip():
            raise ValueError("auth_config.secret_ref is required for authenticated adapters")
        if self.type in {"header", "query"} and not (self.name or "").strip():
            raise ValueError("auth_config.name is required for header/query auth")
        return self


class AdapterRequestConfig(BaseModel):
    _allow_probe_context: ClassVar[bool] = False

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    path: str = "/"
    timeout_s: float | None = Field(None, gt=0, le=300)
    headers: dict[str, Any] | None = None
    query: dict[str, Any] | None = None
    body_template: dict[str, Any] | list[Any] | str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("path cannot be empty")
        return trimmed

    @field_validator("headers", "query", "body_template")
    @classmethod
    def validate_templates(cls, value: Any, info):
        return _ensure_template_paths(
            value,
            f"{cls.__name__}.{info.field_name}",
            allow_probe_context=getattr(cls, "_allow_probe_context", False),
        )


class AdapterSessionCreateExtract(BaseModel):
    session_id: str

    @field_validator("session_id")
    @classmethod
    def validate_json_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed.startswith("$"):
            raise ValueError("session create extract must use a json path starting with '$'")
        return trimmed


class AdapterSessionCreateConfig(AdapterRequestConfig):
    extract: AdapterSessionCreateExtract


class AdapterSessionConfig(BaseModel):
    mode: Literal["per_variant_isolated"] = "per_variant_isolated"
    create: AdapterSessionCreateConfig | None = None
    close: AdapterRequestConfig | None = None


class AdapterInvokeConfig(AdapterRequestConfig):
    model: str | None = None
    system_prompt: str | None = None

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return str(_ensure_template_paths(value, "invoke_config.system_prompt"))


class AdapterResponseExtract(BaseModel):
    mode: Literal["json_paths", "raw_text"] = "json_paths"
    text_path: str | None = None
    error_path: str | None = None
    tool_calls_path: str | None = None

    @model_validator(mode="after")
    def validate_extract(self):
        if self.mode == "raw_text":
            return self
        if not any([self.text_path, self.error_path, self.tool_calls_path]):
            raise ValueError("response_extract must define at least one json path")
        for field_name in ("text_path", "error_path", "tool_calls_path"):
            value = getattr(self, field_name)
            if value and not value.strip().startswith("$"):
                raise ValueError(f"response_extract.{field_name} must start with '$'")
        return self


class ProbeCaptureConfig(BaseModel):
    json_path: str

    @field_validator("json_path")
    @classmethod
    def validate_json_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed.startswith("$"):
            raise ValueError("probe capture json_path must start with '$'")
        return trimmed


class ProbeStepConfig(AdapterRequestConfig):
    _allow_probe_context: ClassVar[bool] = True

    name: str
    captures: dict[str, ProbeCaptureConfig] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("probe step name cannot be empty")
        return trimmed

    @field_validator("captures")
    @classmethod
    def validate_captures(cls, value: dict[str, ProbeCaptureConfig]) -> dict[str, ProbeCaptureConfig]:
        normalized: dict[str, ProbeCaptureConfig] = {}
        for key, capture in value.items():
            name = str(key).strip()
            if not name:
                raise ValueError("probe capture names cannot be empty")
            normalized[name] = capture
        return normalized


ProbeAssertionType = Literal[
    "json_path_exists",
    "json_path_equals",
    "json_path_contains",
    "json_path_not_exists",
    "json_path_not_contains",
    "status_code_is",
    "text_contains",
    "text_not_contains",
]


class ProbeAssertion(BaseModel):
    type: ProbeAssertionType
    step: str | None = None
    path: str | None = None
    expected: Any | None = None
    contains: str | None = None
    status_code: int | None = None

    @model_validator(mode="after")
    def validate_shape(self):
        if self.step is not None and not self.step.strip():
            raise ValueError("probe assertion step cannot be empty")

        if self.type in {"json_path_exists", "json_path_not_exists"}:
            if not (self.path or "").strip().startswith("$"):
                raise ValueError(f"{self.type} requires path starting with '$'")
        elif self.type == "json_path_equals":
            if not (self.path or "").strip().startswith("$"):
                raise ValueError("json_path_equals requires path starting with '$'")
            if self.expected is None:
                raise ValueError("json_path_equals requires expected")
        elif self.type in {"json_path_contains", "json_path_not_contains"}:
            if not (self.path or "").strip().startswith("$"):
                raise ValueError(f"{self.type} requires path starting with '$'")
            if not (self.contains or "").strip():
                raise ValueError(f"{self.type} requires contains")
        elif self.type == "status_code_is":
            if self.status_code is None:
                raise ValueError("status_code_is requires status_code")
        elif self.type in {"text_contains", "text_not_contains"}:
            if not (self.contains or "").strip():
                raise ValueError(f"{self.type} requires contains")
        return self


class AdapterProbeConfig(BaseModel):
    enabled: bool = True
    steps: list[ProbeStepConfig] = Field(default_factory=list)
    assertions: list[ProbeAssertion] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_probe(self):
        if not self.steps:
            raise ValueError("probe_config.steps cannot be empty")
        if not self.assertions:
            raise ValueError("probe_config.assertions cannot be empty")

        step_names: list[str] = []
        for step in self.steps:
            if step.name in step_names:
                raise ValueError(f"Duplicate probe step name: {step.name}")
            step_names.append(step.name)

        valid_steps = set(step_names)
        for assertion in self.assertions:
            if assertion.step and assertion.step not in valid_steps:
                raise ValueError(f"Probe assertion references unknown step: {assertion.step}")
        return self


class AdapterBase(BaseModel):
    name: str
    description: str | None = None
    mode: Literal["direct_http_adapter"] = "direct_http_adapter"
    transport: Literal["http_json", "openai_chat"]
    base_url: str
    auth_config: AdapterAuthConfig = Field(default_factory=AdapterAuthConfig)
    session_config: AdapterSessionConfig | None = Field(default_factory=AdapterSessionConfig)
    invoke_config: AdapterInvokeConfig
    response_extract: AdapterResponseExtract
    probe_config: AdapterProbeConfig | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("name cannot be empty")
        return trimmed

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        trimmed = value.strip().rstrip("/")
        if not trimmed:
            raise ValueError("base_url cannot be empty")
        if not trimmed.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return trimmed


class AdapterCreate(AdapterBase):
    pass


class AdapterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    mode: Literal["direct_http_adapter"] | None = None
    transport: Literal["http_json", "openai_chat"] | None = None
    base_url: str | None = None
    auth_config: AdapterAuthConfig | None = None
    session_config: AdapterSessionConfig | None = None
    invoke_config: AdapterInvokeConfig | None = None
    response_extract: AdapterResponseExtract | None = None
    probe_config: AdapterProbeConfig | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("name cannot be empty")
        return trimmed

    @field_validator("base_url")
    @classmethod
    def validate_optional_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip().rstrip("/")
        if not trimmed.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return trimmed


class AdapterResponse(AdapterBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdapterTestStep(BaseModel):
    name: str
    ok: bool
    detail: str | None = None
    status_code: int | None = None


class AdapterTestRequest(BaseModel):
    adapter_id: str | None = None
    adapter: AdapterCreate | None = None
    prompt: str = "Adapter test prompt"
    history: list[dict[str, Any]] = Field(default_factory=list)
    runtime_vars: dict[str, Any] = Field(default_factory=dict)
    variant_type: str = "attack"
    scan_id: str | None = "adapter-test"
    case_id: str | None = "adapter-test-case"

    @model_validator(mode="after")
    def validate_request(self):
        if not self.adapter_id and not self.adapter:
            raise ValueError("Either adapter_id or adapter must be provided")
        if self.adapter_id and self.adapter:
            raise ValueError("Provide adapter_id or adapter, not both")
        return self


class AdapterTestResponse(BaseModel):
    success: bool
    response_status: str
    response_text: str | None = None
    response_error: str | None = None
    session_id: str | None = None
    transport_meta: dict[str, Any] = Field(default_factory=dict)
    rendered_request: dict[str, Any] | None = None
    steps: list[AdapterTestStep] = Field(default_factory=list)


class ProbeStepResult(BaseModel):
    name: str
    ok: bool
    status_code: int | None = None
    failure_type: str | None = None
    failure_reason: str | None = None
    captures: dict[str, Any] = Field(default_factory=dict)
    rendered_request: dict[str, Any] | None = None
    response_preview: str | None = None


class ProbeAssertionResult(BaseModel):
    type: ProbeAssertionType | str
    step: str | None = None
    ok: bool
    actual: Any | None = None
    expected: Any | None = None
    failure_reason: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ProbeEvidence(BaseModel):
    step: str
    kind: str
    value: Any | None = None


class ProbeTestRequest(BaseModel):
    adapter_id: str | None = None
    adapter: AdapterCreate | None = None
    probe_config: AdapterProbeConfig | None = None
    runtime_vars: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    variant_type: str = "attack"
    scan_id: str | None = "probe-test-scan"
    case_id: str | None = "probe-test-case"

    @model_validator(mode="after")
    def validate_request(self):
        if not self.adapter_id and not self.adapter:
            raise ValueError("Either adapter_id or adapter must be provided")
        if self.adapter_id and self.adapter:
            raise ValueError("Provide adapter_id or adapter, not both")
        return self


class ProbeTestResponse(BaseModel):
    success: bool
    verified: bool
    assertion_results: list[ProbeAssertionResult] = Field(default_factory=list)
    evidence: list[ProbeEvidence] = Field(default_factory=list)
    failure_reason: str | None = None
    failure_type: str | None = None
    step_results: list[ProbeStepResult] = Field(default_factory=list)


class AdapterProbeTestResponse(ProbeTestResponse):
    pass
