from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
import io
import json
import logging
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from models.semantic_ai_shadow import SemanticAIFailure as Failure
from models.structured_interpretation import RegisteredSourceRef, SourceRefClass, ValidationStatus
from services.ai.openai_semantic_interpreter import (
    OpenAISemanticEvidenceInterpreter, SemanticShadowConfig, SemanticTransportReply,
    read_semantic_shadow_config, compare_semantic_shadow, shadow_diagnostics,
    _OpenAIResponsesTransport,
)
from services.ai.semantic_shadow_request import prepare_semantic_request, PROMPT_VERSION
from services.fixture_semantic_interpreter import FixtureSemanticInterpreter
from services.semantic_evidence_boundary import signature
from scripts.run_semantic_ai_shadow import main, selected_case, CASE_IDS
from tests.semantic_evidence_v1_runner import project, references, response


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("External IO is forbidden")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    from services import database
    monkeypatch.setattr(database, "get_connection", deny)
    from services.ai import openai_client
    monkeypatch.setattr(openai_client, "OpenAI", deny)


def request(case_id="SE01"):
    case = next(c for c in references() if c["id"] == case_id)
    return project({k: v for k, v in case.items() if k != "expected"})


def wire(req, relation="direct", coverage="full"):
    prepared = prepare_semantic_request(req, "fake-model")
    reason = {"none": "no_support", "uncertain": "insufficient_information"}.get(relation,
        "partial_support" if coverage == "partial" else relation + "_support")
    needs = []
    for need in prepared.need_ids:
        needs.append(dict(need_id=need, support_relation=relation, coverage=coverage,
            confidence="unknown" if relation == "uncertain" else "high", reason_code=reason, joint_support=False,
            links=[dict(need_id=need, evidence_ref=ref, candidate_capability_id=None,
                support_relation=relation, coverage=coverage, confidence="high", reason_code=reason)
                for ref in prepared.evidence_ids]))
    return {"needs": needs}


class FakeTransport:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def execute(self, payload):
        self.calls.append(deepcopy(payload))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def adapter(raw=None, *, req=None, reply=None, config=None):
    req = req or request()
    fake = FakeTransport(reply if reply is not None else SemanticTransportReply("completed", json.dumps(raw or wire(req))))
    made = []
    def factory(model):
        made.append(model)
        return fake
    obj = OpenAISemanticEvidenceInterpreter(config or SemanticShadowConfig(True, "fake-model"), transport_factory=factory,
        clock=lambda: "2026-09-17T00:00:00+00:00", timer=lambda: 1.0)
    return obj, fake, made


@pytest.mark.parametrize("enabled,authorized,model,failure", [
    (False, False, "fake-model", Failure.DISABLED),
    (True, False, "fake-model", Failure.NOT_AUTHORIZED),
    (False, True, "fake-model", Failure.DISABLED),
    (True, True, "", Failure.MODEL_NOT_CONFIGURED),
    (True, "true", "fake-model", Failure.NOT_AUTHORIZED),
])
def test_double_lock_prevents_even_client_construction(enabled, authorized, model, failure):
    obj, fake, made = adapter(config=SemanticShadowConfig(enabled, model))
    result = obj.evaluate(request(), allow_external_ai=authorized)
    assert result.failure is failure and result.response is None and result.result is None
    assert not fake.calls and not made


def test_default_and_protocol_call_cannot_spend(monkeypatch):
    monkeypatch.setenv("REAL_AI_SEMANTIC_SHADOW_ENABLED", "true")
    monkeypatch.setenv("SEMANTIC_SHADOW_MODEL", "fake-model")
    assert OpenAISemanticEvidenceInterpreter().evaluate(request(), allow_external_ai=True).failure is Failure.DISABLED
    obj, fake, made = adapter()
    assert obj.evaluate_semantic_support(request()) is None
    assert not fake.calls and not made


def test_config_environment_and_injected_secrets_without_model_fallback():
    assert read_semantic_shadow_config({}, {}).model == ""
    cfg = read_semantic_shadow_config({"SEMANTIC_SHADOW_MODEL": " env-model "},
                                     {"SEMANTIC_SHADOW_MODEL": "secret-model", "REAL_AI_SEMANTIC_SHADOW_ENABLED": True})
    assert cfg == SemanticShadowConfig(True, "env-model")
    assert not read_semantic_shadow_config({"REAL_AI_SEMANTIC_SHADOW_ENABLED": "1"}).enabled
    class MissingSecrets:
        def get(self, key):
            raise RuntimeError("PRIVATE SECRET")
    assert read_semantic_shadow_config({}, MissingSecrets()) == SemanticShadowConfig()


def test_fake_direct_success_and_safe_usage_metadata():
    req = request()
    reply = SemanticTransportReply("completed", json.dumps(wire(req)), request_id="req_fake", input_tokens=120, output_tokens=80, total_tokens=200)
    obj, fake, made = adapter(reply=reply)
    run = obj.evaluate(req, allow_external_ai=True)
    assert run.failure is None and run.result.needs[0].assessment.value == "proven"
    assert run.result.status is ValidationStatus.ACCEPTED
    assert len(fake.calls) == 1 and made == ["fake-model"]
    assert (run.metadata.input_tokens, run.metadata.output_tokens, run.metadata.total_tokens) == (120, 80, 200)
    assert run.metadata.provider_request_id == "req_fake" and run.metadata.latency_ms == 0
    assert not run.authoritative and not run.metadata.authoritative


@pytest.mark.parametrize("ref", ["unknown-ref", "checkpoint:v1", "fact", "another-candidate:e0", "e0", ""])
def test_provider_ids_must_be_supplied_aliases_then_pass_authority(ref):
    raw = wire(request())
    raw["needs"][0]["links"][0]["evidence_ref"] = ref
    obj, fake, _ = adapter(raw)
    run = obj.evaluate(request(), allow_external_ai=True)
    assert run.failure is Failure.AUTHORITY_VALIDATION_FAILED and run.response is None
    assert run.result.issue_codes == ("unknown_ref",)
    assert len(fake.calls) == 1


@pytest.mark.parametrize("case_id,relation,coverage,state", [
    ("SE05", "none", "none", "evidence_missing"),
    ("SE10", "direct", "partial", "evidence_missing"),
    ("SE03", "adjacent", "full", "transferable"),
    ("SE31", "uncertain", "unknown", "evidence_missing"),
])
def test_existing_semantic_normalization_remains_authoritative(case_id, relation, coverage, state):
    req = request(case_id)
    obj, _, _ = adapter(wire(req, relation, coverage), req=req)
    run = obj.evaluate(req, allow_external_ai=True)
    assert run.failure is None
    assert run.result.needs[0].assessment.value == state


def test_declared_adjacent_cannot_be_promoted_to_direct_ownership():
    req = request("SE14")
    raw = wire(req, "adjacent", "full")
    raw["needs"][0].update(support_relation="direct", reason_code="direct_support")
    obj, _, _ = adapter(raw, req=req)
    run = obj.evaluate(req, allow_external_ai=True)
    assert run.result.needs[0].assessment.value == "transferable"
    assert "ownership_promotion" in run.result.issue_codes


@pytest.mark.parametrize("reply,failure", [
    (RuntimeError("PRIVATE provider key=secret prompt=private"), Failure.PROVIDER_ERROR),
    (TimeoutError("PRIVATE request timeout"), Failure.TIMEOUT),
    (SemanticTransportReply("completed", "not json PRIVATE"), Failure.INVALID_STRUCTURED_OUTPUT),
    (SemanticTransportReply("completed", "PRIVATE refusal", True), Failure.REFUSAL),
    (SemanticTransportReply("incomplete", "PRIVATE partial JSON"), Failure.INCOMPLETE_RESPONSE),
    (SemanticTransportReply("failed", "PRIVATE error"), Failure.PROVIDER_ERROR),
])
def test_provider_failures_abstain_once_and_never_log_content(reply, failure, caplog):
    obj, fake, _ = adapter(reply=reply)
    with caplog.at_level(logging.DEBUG):
        run = obj.evaluate(request(), allow_external_ai=True)
    assert run.failure is failure and run.response is None and run.result is None
    assert len(fake.calls) == 1
    assert "PRIVATE" not in caplog.text
    assert "PRIVATE" not in json.dumps(shadow_diagnostics(run))


@pytest.mark.parametrize("variant", ["extra", "duplicate_json", "missing", "coercion", "omitted_source", "facet", "reasoning"])
def test_strict_wire_schema_rejects_malformed_output(variant):
    raw = wire(request())
    if variant == "extra":
        raw["authoritative"] = True
    elif variant == "missing":
        raw["needs"][0].pop("coverage")
    elif variant == "coercion":
        raw["needs"][0]["joint_support"] = "true"
    elif variant == "omitted_source":
        raw["needs"][0]["links"] = []
    elif variant == "facet":
        raw["needs"][0]["supported_facet_ids"] = ["invented"]
    elif variant == "reasoning":
        raw["chain_of_thought"] = "PRIVATE"
    text = '{"needs": [], "needs": []}' if variant == "duplicate_json" else json.dumps(raw)
    obj, fake, _ = adapter(reply=SemanticTransportReply("completed", text))
    assert obj.evaluate(request(), allow_external_ai=True).failure is Failure.INVALID_STRUCTURED_OUTPUT
    assert len(fake.calls) == 1


def test_invalid_input_and_missing_client_make_no_request():
    req = request()
    invalid = replace(req, context=replace(req.context, candidate_id="foreign"))
    obj, fake, made = adapter()
    assert obj.evaluate(invalid, allow_external_ai=True).failure is Failure.REQUEST_BUILD_FAILED
    assert not made and not fake.calls
    def fail_client(model):
        raise ValueError("PRIVATE KEY")
    obj = OpenAISemanticEvidenceInterpreter(SemanticShadowConfig(True, "fake-model"), transport_factory=fail_client)
    assert obj.evaluate(req, allow_external_ai=True).failure is Failure.PROVIDER_CLIENT_UNAVAILABLE


def test_request_minimizes_source_data_and_uses_strict_nonpersistent_response():
    req = request()
    context = req.context
    candidate = replace(context.candidate_profile, source_refs=(*context.candidate_profile.source_refs, "unrelated"),
        checkpoint=replace(context.candidate_profile.checkpoint, current_position="PRIVATE CHECKPOINT"),
        evidence_summaries=("PRIVATE WHOLE CV",), preferences=("PRIVATE EMAIL user@example.test",),
        capabilities=(*context.candidate_profile.capabilities, replace(context.candidate_profile.capabilities[0],
            capability_id="unrelated-cap", label="PRIVATE UNRELATED", evidence_refs=("unrelated",))))
    req = replace(req, context=replace(context, candidate_profile=candidate,
        job_profile=replace(context.job_profile, context="PRIVATE WHOLE JOB DESCRIPTION"),
        memory_projection={"secret": "PRIVATE KEY"}, source_registry=(*context.source_registry,
            RegisteredSourceRef("unrelated", SourceRefClass.CANDIDATE_EVIDENCE, context.candidate_id, "professional_experience", True))))
    prepared = prepare_semantic_request(req, "fake-model")
    serialized = json.dumps(prepared.payload)
    assert "PRIVATE" not in serialized and "user@example.test" not in serialized and "unrelated" not in serialized
    assert req.evidence[0].summary in serialized
    assert '"candidate_id"' not in serialized and '"input_signature"' not in serialized
    assert not prepared.payload["store"] and not prepared.payload["background"] and not prepared.payload["stream"]
    assert prepared.payload["truncation"] == "disabled"
    fmt = prepared.payload["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"]
    def inspect(schema):
        if schema.get("type") == "object":
            assert not schema["additionalProperties"]
            assert set(schema["required"]) == set(schema["properties"])
            for child in schema["properties"].values():
                inspect(child)
        if "items" in schema:
            inspect(schema["items"])
        for child in schema.get("anyOf", []):
            inspect(child)
    inspect(fmt["schema"])
    assert PROMPT_VERSION in prepared.payload["instructions"]


def test_sdk_transport_reuses_existing_client_with_finite_timeout_and_zero_retries():
    calls = []
    response = SimpleNamespace(status="completed", output=[], output_text='{"needs":[]}', usage=None, _request_id="req_fake")
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs) or response))
    def options(**kwargs):
        assert kwargs == {"max_retries": 0, "timeout": 30.0}
        return client
    transport = _OpenAIResponsesTransport(SimpleNamespace(client=SimpleNamespace(with_options=options)))
    assert transport.execute({"store": False}).request_id == "req_fake"
    assert calls == [{"store": False}]


def test_existing_client_factory_is_lazy_and_model_is_explicit(monkeypatch):
    from services.ai import openai_client
    calls = []
    reply = SimpleNamespace(status="completed", output=[], output_text=json.dumps(wire(request())), usage=None, _request_id=None)
    sdk = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs) or reply))
    made = []
    class FakeApplicationClient:
        def __init__(self, model):
            made.append(model)
            self.client = SimpleNamespace(with_options=lambda **kwargs: sdk)
    monkeypatch.setattr(openai_client, "OpenAIClient", FakeApplicationClient)
    obj = OpenAISemanticEvidenceInterpreter(SemanticShadowConfig(True, "fake-model"))
    assert not made
    assert obj.evaluate(request(), allow_external_ai=True).failure is None
    assert made == ["fake-model"] and len(calls) == 1


def test_shadow_comparison_is_content_free_non_authoritative_and_absence_not_match():
    req, expected = selected_case("SE01")
    obj, _, _ = adapter(req=req)
    run = obj.evaluate(req, allow_external_ai=True)
    record = compare_semantic_shadow(run, expected)[0]
    assert record.same_relation and record.same_coverage and not record.authoritative
    with pytest.raises(FrozenInstanceError):
        record.authoritative = True
    with pytest.raises(ValueError):
        replace(record, authoritative=True)
    assert req.evidence[0].summary not in json.dumps(asdict(record))
    disabled = OpenAISemanticEvidenceInterpreter().evaluate(req)
    assert compare_semantic_shadow(disabled, expected)[0].same_relation is None


def test_fixtures_still_work_without_real_adapter():
    req = request()
    raw = response("SE01", req)
    result = FixtureSemanticInterpreter({signature(req): raw}).evaluate(req)
    assert result.status is ValidationStatus.ACCEPTED


@pytest.mark.parametrize("args", [[], ["--confirm-external-ai"], ["--cases", "SE01"]])
def test_dry_run_never_constructs_transport_even_with_feature_enabled(args):
    def forbidden(model):
        pytest.fail("Transport construction forbidden in dry-run")
    stream = io.StringIO()
    assert main(args, config=SemanticShadowConfig(True, "fake-model"), transport_factory=forbidden, output=stream) == 0
    plan = json.loads(stream.getvalue())
    assert plan["executed_requests"] == 0
    assert plan["planned_requests"] == (1 if args and args[0] == "--cases" else 8)


@pytest.mark.parametrize("args,config", [
    (["--live"], SemanticShadowConfig(True, "fake-model")),
    (["--live", "--cases", "SE01"], SemanticShadowConfig(True, "fake-model")),
    (["--live", "--confirm-external-ai"], SemanticShadowConfig(True, "fake-model")),
    (["--live", "--confirm-external-ai", "--cases", "SE01"], SemanticShadowConfig(False, "fake-model")),
    (["--live", "--confirm-external-ai", "--cases", "SE01"], SemanticShadowConfig(True, "")),
])
def test_harness_missing_authorizations_never_reach_transport(args, config):
    def forbidden(model):
        pytest.fail("Unauthorized transport construction")
    assert main(args, config=config, transport_factory=forbidden, output=io.StringIO()) == 2


def test_frozen_batch_and_duplicate_rejection():
    manifest = json.loads((Path(__file__).parents[1] / "scripts/semantic_shadow_first_batch.json").read_text())
    assert tuple(manifest["case_ids"]) == CASE_IDS
    assert manifest["maximum_requests"] == len(CASE_IDS) == 8
    assert not manifest["live_executed"]
    assert main(["--cases", "SE01", "SE01"], output=io.StringIO()) == 2


def test_fully_authorized_harness_uses_only_injected_fake_and_stops_on_failure():
    fake = FakeTransport(TimeoutError("PRIVATE"))
    stream = io.StringIO()
    assert main(["--live", "--confirm-external-ai", "--cases", "SE01", "SE03"],
                config=SemanticShadowConfig(True, "fake-model"), transport_factory=lambda model: fake, output=stream) == 1
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert lines[0]["planned_requests"] == 2 and lines[0]["executed_requests"] == 0
    assert len(fake.calls) == 1 and len(lines) == 2
    assert "PRIVATE" not in stream.getvalue()


def test_sdk_debug_payload_logs_suppressed_only_during_shadow_transport(caplog):
    reply = SemanticTransportReply("completed", json.dumps(wire(request())))
    class LoudFake:
        def execute(self, payload):
            logging.getLogger("openai._base_client").debug("PRIVATE %s", payload)
            logging.getLogger("httpx").warning("PRIVATE headers")
            return reply
    obj = OpenAISemanticEvidenceInterpreter(SemanticShadowConfig(True, "fake-model"), transport_factory=lambda model: LoudFake())
    with caplog.at_level(logging.DEBUG):
        assert obj.evaluate(request(), allow_external_ai=True).failure is None
        logging.getLogger("openai._base_client").debug("outside-shadow-marker")
    assert "PRIVATE" not in caplog.text
    assert "outside-shadow-marker" in caplog.text
    assert request().evidence[0].summary not in caplog.text


def test_invalid_usage_and_request_id_are_not_echoed():
    reply = SemanticTransportReply("completed", json.dumps(wire(request())), request_id="PRIVATE email@example.test",
        input_tokens=-1, output_tokens=True, total_tokens="PRIVATE")
    obj, _, _ = adapter(reply=reply)
    metadata = obj.evaluate(request(), allow_external_ai=True).metadata
    assert metadata.provider_request_id is None
    assert metadata.input_tokens is metadata.output_tokens is metadata.total_tokens is None


def test_av06_preserves_reuse_but_never_tax_proof():
    req, expected = selected_case("AV06")
    raw = wire(req)
    raw["needs"][1].update(support_relation="none", coverage="none", reason_code="no_support")
    raw["needs"][1]["links"][0].update(support_relation="none", coverage="none", reason_code="no_support")
    obj, _, _ = adapter(raw, req=req)
    run = obj.evaluate(req, allow_external_ai=True)
    assert [n.assessment.value for n in run.result.needs] == ["proven", "evidence_missing"]
    assert all(c.same_relation and c.same_coverage for c in compare_semantic_shadow(run, expected))


def test_adapter_has_no_production_callers():
    root = Path(__file__).parents[1]
    for path in [root / "app.py", root / "streamlit_app.py", *list((root / "pages").glob("*.py"))]:
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "openai_semantic_interpreter" not in text
