"""Opt-in shadow adapter. One isolated transport call, zero automatic retries."""
from dataclasses import asdict, dataclass, replace
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
import os
import time
import threading
from typing import Protocol

from models.semantic_ai_shadow import SemanticAIFailure as Failure, SemanticShadowMetadata, SemanticShadowRun, SemanticShadowComparison
from models.semantic_evidence import SemanticSupportResponse, SemanticSupportResult
from models.structured_interpretation import ValidationStatus
from services.ai.semantic_shadow_request import prepare_semantic_request, parse_semantic_response
from services.semantic_evidence_boundary import signature, validate_semantic_support
from services.structured_interpretation_validation import InterpretationValidationError


@dataclass(frozen=True)
class SemanticShadowConfig:
    enabled: bool = False
    model: str = ""

    def __post_init__(self):
        if type(self.enabled) is not bool or not isinstance(self.model, str):
            raise ValueError("invalid_semantic_shadow_configuration")
        object.__setattr__(self, "model", self.model.strip())


def read_semantic_shadow_config(environ=None, secrets=None):
    """Environment first, optional injected Streamlit secrets second; no key lookup."""
    env = os.environ if environ is None else environ
    def value(name):
        raw = env.get(name)
        if raw is None or not str(raw).strip():
            try:
                raw = secrets.get(name) if secrets is not None else None
            except Exception:
                raw = None
        return str(raw).strip() if raw is not None else ""
    return SemanticShadowConfig(value("REAL_AI_SEMANTIC_SHADOW_ENABLED").lower() == "true",
                                value("SEMANTIC_SHADOW_MODEL"))


@dataclass(frozen=True)
class SemanticTransportReply:
    status: str
    output_text: str = ""
    refusal: bool = False
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    returned_model: str | None = None


class SemanticTransport(Protocol):
    def execute(self, payload: dict) -> SemanticTransportReply: ...


class _OpenAIResponsesTransport:
    def __init__(self, application_client):
        self._client = application_client.client.with_options(max_retries=0, timeout=30.0)

    def execute(self, payload):
        from openai import APITimeoutError
        try:
            response = self._client.responses.create(**payload)
        except APITimeoutError:
            raise TimeoutError("semantic_shadow_timeout") from None
        refusal = any(getattr(part, "type", None) == "refusal"
                      for item in (response.output or ()) for part in (getattr(item, "content", None) or ()))
        usage = response.usage
        return SemanticTransportReply(response.status, response.output_text, refusal,
            getattr(response, "_request_id", None), getattr(usage, "input_tokens", None),
            getattr(usage, "output_tokens", None), getattr(usage, "total_tokens", None),
            getattr(response, "model", None))


def _build_transport(model):
    # The existing application's client owns SDK construction and API-key resolution.
    # This factory is reached only after both approvals and successful preparation.
    from services.ai.openai_client import OpenAIClient
    return _OpenAIResponsesTransport(OpenAIClient(model=model))


def _tokens(value):
    return value if type(value) is int and value >= 0 else None


def _request_id(value):
    if isinstance(value, str) and value.startswith("req_") and len(value) <= 128 and all(
        char.isascii() and (char.isalnum() or char in "_-") for char in value
    ):
        return value
    return None


@contextmanager
def _private_transport_logs():
    # The installed SDK logs full request options at DEBUG. Suppress only transport
    # loggers on this thread, preserving unrelated application logs and other callers.
    owner = threading.get_ident()
    class PrivateCall(logging.Filter):
        def filter(self, record):
            return record.thread != owner
    guard = PrivateCall()
    names = {"openai._base_client", "httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2", "httpcore.proxy",
             "urllib3.connectionpool", "requests_oauthlib.oauth2_session", "oauthlib.oauth2.rfc6749.clients.base",
             "googleapiclient.http", "googleapiclient.discovery", "google.auth.transport.requests"}
    names.update(name for name in list(logging.Logger.manager.loggerDict)
                 if name.startswith(("openai.", "httpx.", "httpcore.", "urllib3.", "google.auth.",
                                     "googleapiclient.", "requests_oauthlib.", "oauthlib.")))
    loggers = [logging.getLogger(name) for name in names]
    for logger in loggers:
        logger.addFilter(guard)
    try:
        yield
    finally:
        for logger in loggers:
            logger.removeFilter(guard)


class OpenAISemanticEvidenceInterpreter:
    def __init__(self, config=None, *, transport_factory=None, clock=None, timer=None):
        self.config = config if config is not None else SemanticShadowConfig()
        self._transport_factory = transport_factory or _build_transport
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._timer = timer or time.monotonic

    def prepare(self, request):
        return prepare_semantic_request(request, self.config.model)

    def evaluate_semantic_support(self, request, *, allow_external_ai=False):
        return self.evaluate(request, allow_external_ai=allow_external_ai).response

    def evaluate(self, request, *, allow_external_ai=False):
        metadata = SemanticShadowMetadata(self.config.model or None, "", self._clock())
        def finish(failure=None, result=None, response=None):
            run = SemanticShadowRun(metadata, failure, result, response)
            logging.getLogger(__name__).info("semantic_ai_shadow result=%s validation=%s issues=%d",
                failure.value if failure else "completed", result.status.value if result else "unavailable",
                len(result.issue_codes) if result else 0)
            return run
        if not self.config.enabled:
            return finish(Failure.DISABLED)
        if allow_external_ai is not True:
            return finish(Failure.NOT_AUTHORIZED)
        if not self.config.model:
            return finish(Failure.MODEL_NOT_CONFIGURED)
        try:
            prepared = self.prepare(request)
            metadata = replace(metadata, input_signature=signature(prepared.request))
        except Exception:
            return finish(Failure.REQUEST_BUILD_FAILED)
        try:
            with _private_transport_logs():
                transport = self._transport_factory(self.config.model)
            if transport is None:
                return finish(Failure.PROVIDER_CLIENT_UNAVAILABLE)
        except Exception:
            return finish(Failure.PROVIDER_CLIENT_UNAVAILABLE)
        start = self._timer()
        try:
            with _private_transport_logs():
                reply = transport.execute(prepared.payload)
        except TimeoutError:
            metadata = replace(metadata, latency_ms=max(0, int((self._timer() - start) * 1000)))
            return finish(Failure.TIMEOUT)
        except Exception:
            metadata = replace(metadata, latency_ms=max(0, int((self._timer() - start) * 1000)))
            return finish(Failure.PROVIDER_ERROR)
        metadata = replace(metadata, latency_ms=max(0, int((self._timer() - start) * 1000)))
        if not isinstance(reply, SemanticTransportReply):
            return finish(Failure.INVALID_STRUCTURED_OUTPUT)
        metadata = replace(metadata, provider_request_id=_request_id(reply.request_id),
            input_tokens=_tokens(reply.input_tokens), output_tokens=_tokens(reply.output_tokens), total_tokens=_tokens(reply.total_tokens),
            returned_model=reply.returned_model if isinstance(reply.returned_model, str) and
                0 < len(reply.returned_model) <= 128 and all(c.isascii() and (c.isalnum() or c in '._-') for c in reply.returned_model) else None)
        if reply.refusal:
            return finish(Failure.REFUSAL)
        if reply.status == "failed":
            return finish(Failure.PROVIDER_ERROR)
        if reply.status != "completed":
            return finish(Failure.INCOMPLETE_RESPONSE)
        try:
            response = parse_semantic_response(prepared, reply.output_text)
        except InterpretationValidationError as error:
            # Unknown IDs remain authority failures, not structural success.
            authority = error.code.value in {"unknown_ref", "unknown_need", "unknown_capability"}
            invalid = SemanticSupportResult(metadata.input_signature, ValidationStatus.REJECTED, issue_codes=(error.code.value,))
            return finish(Failure.AUTHORITY_VALIDATION_FAILED if authority else Failure.INVALID_STRUCTURED_OUTPUT, result=invalid)
        except Exception:
            return finish(Failure.INVALID_STRUCTURED_OUTPUT)
        result = validate_semantic_support(prepared.request, response)
        if result.status not in {ValidationStatus.ACCEPTED, ValidationStatus.NORMALIZED}:
            return finish(Failure.AUTHORITY_VALIDATION_FAILED, result=result)
        # Retain normalized domain data only. Raw provider content never leaves this method.
        normalized = SemanticSupportResponse(response.input_signature, response.interpreter_version,
                                             tuple(item.support for item in result.needs))
        return finish(result=result, response=normalized)


def compare_semantic_shadow(run, references):
    """References are comparison-only and are never sent in provider requests."""
    actual = {item.support.need_id: item.support for item in run.result.needs} if run.result else {}
    records = []
    for need_id in sorted(set(references) | set(actual)):
        expected = references.get(need_id)
        observed = actual.get(need_id)
        relation = observed.support_relation if observed else None
        coverage = observed.coverage if observed else None
        records.append(SemanticShadowComparison(run.metadata, need_id,
            expected[0] if expected else None, relation,
            expected[0] == relation if expected and observed else None,
            expected[1] if expected else None, coverage,
            expected[1] == coverage if expected and observed else None,
            run.result.status.value if run.result else "unavailable",
            run.result.issue_codes if run.result else ((run.failure.value,) if run.failure else ())))
    return tuple(records)


def shadow_diagnostics(run):
    """Allowlist only; never serialize the request, response or semantic hint fields."""
    return {**asdict(run.metadata), "failure": run.failure.value if run.failure else None,
            "validation_status": run.result.status.value if run.result else "unavailable",
            "issue_codes": run.result.issue_codes if run.result else ((run.failure.value,) if run.failure else ()), "authoritative": False}
