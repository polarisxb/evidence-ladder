from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class QuartetVariantSet(BaseModel):
    attack: str
    clean: str
    quoted_attack: str
    benign_distractor: str


class QuartetPrompts(BaseModel):
    case_id: str
    category: str
    variants: QuartetVariantSet
    protocol_version: Literal["quartet_v1"] = "quartet_v1"
    owasp_id: str | None = None
    template_id: str | None = None
    template_name: str | None = None
    payload_language: str | None = None
    payload_variant: str | None = None


class SuiteManifest(BaseModel):
    suite_version: str
    generated_at: datetime
    case_count: int
    content_hash: str
    protocol_version: Literal["quartet_v1"] = "quartet_v1"
    description: str | None = None


class BenchmarkSuite(BaseModel):
    manifest: SuiteManifest
    cases: list[QuartetPrompts]
