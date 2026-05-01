from pydantic import BaseModel, Field


class ResponseEvaluationResponse(BaseModel):
    response_origin: str | None = None
    origin_confidence: str | None = None
    evaluation_validity: str | None = None
    invalid_reason: str | None = None
    matched_signature: str | None = None
    transport_ok: bool | None = None
    http_status: int | None = None
    content_type: str | None = None
    evidence_codes: list[str] = Field(default_factory=list)
    baseline_probe: dict | None = None
    # Two-dimensional Provenance fields
    model_invoked: bool | None = None
    post_processed: bool | None = None
    block_reason: str | None = None
    post_reason: str | None = None
    provenance_source: str | None = None
