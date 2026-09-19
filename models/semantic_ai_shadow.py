"""Content-free shadow metadata; provider SDK types never enter domain models."""
from dataclasses import dataclass, field
from enum import Enum

from models.semantic_evidence import (
    SemanticSupportResponse, SemanticSupportResult, SemanticSupportRelation, SemanticCoverage,
)


class SemanticAIFailure(str, Enum):
    DISABLED = "disabled"
    NOT_AUTHORIZED = "not_authorized"
    MODEL_NOT_CONFIGURED = "model_not_configured"
    PROVIDER_CLIENT_UNAVAILABLE = "provider_client_unavailable"
    REQUEST_BUILD_FAILED = "request_build_failed"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    REFUSAL = "refusal"
    INCOMPLETE_RESPONSE = "incomplete_response"
    INVALID_STRUCTURED_OUTPUT = "invalid_structured_output"
    AUTHORITY_VALIDATION_FAILED = "authority_validation_failed"


@dataclass(frozen=True)
class SemanticShadowMetadata:
    model: str | None
    input_signature: str
    created_at: str
    prompt_version: str = "semantic-support-prompt-v2"
    adapter_version: str = "openai-semantic-shadow-v1"
    operation: str = "semantic_evidence_support"
    schema_version: str = "semantic-ai-shadow-v1"
    latency_ms: int | None = None
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    returned_model: str | None = None
    authoritative: bool = field(default=False, init=False)


@dataclass(frozen=True)
class SemanticShadowRun:
    metadata: SemanticShadowMetadata
    failure: SemanticAIFailure | None = None
    result: SemanticSupportResult | None = None
    response: SemanticSupportResponse | None = None
    authoritative: bool = field(default=False, init=False)


@dataclass(frozen=True)
class SemanticShadowComparison:
    metadata: SemanticShadowMetadata
    need_id: str
    reference_relation: SemanticSupportRelation | None
    ai_relation: SemanticSupportRelation | None
    same_relation: bool | None
    reference_coverage: SemanticCoverage | None
    ai_coverage: SemanticCoverage | None
    same_coverage: bool | None
    validation_status: str
    issue_codes: tuple[str, ...]
    authoritative: bool = field(default=False, init=False)
