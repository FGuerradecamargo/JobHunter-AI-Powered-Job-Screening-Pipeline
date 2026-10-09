import copy
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from models.candidate import Candidate
from models.company_interview import (
    V3_VERSION, V4_VERSION, V4_QUESTIONS, V4_ADAPTIVE_QUESTIONS,
    ConfirmedCompanyAnswer, validate_answers, validate_single_answer,
)
from services.candidate_repository import CandidateRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from services.company_interview import (
    start_interview, current_question, confirm_text, skip_question, resume_interview,
    transcribe_voice, confirm_voice_transcript, discard_voice, save_correction,
    finalize, set_adaptive_dimensions,
)
from services.company_reflection import (
    reflection_request_v4, build_reflection_prompt_v4, parse_reflection_v4, reflect_v4,
)


@pytest.fixture
def repo():
    for cid in ("a", "b"):
        CandidateRepository().save(Candidate(cid, "Synthetic", "", "", ""))
    return CandidateOnboardingRepository()


def start(repo, **changes):
    args = dict(scope="scope", candidate_id="a", company="Synthetic", role="Analyst",
                start_date="2020-01", end_date=None, version=V4_VERSION, repository=repo)
    return start_interview(**(args | changes))


def base(repo):
    draft = start(repo)
    for i in range(3):
        confirm_text(draft, "scope", repo, f"Original source {i}")
    return draft


def output(dimension=None, status="SUFFICIENT"):
    coverage = dict.fromkeys(V4_ADAPTIVE_QUESTIONS, status)
    if dimension in coverage:
        coverage[dimension] = "INSUFFICIENT"
    return dict(coverage=coverage, next_missing_dimension=dimension)


def reflect(draft, dimension=None):
    provider = Mock()
    provider.generate.return_value = json.dumps(output(dimension))
    reflect_v4(draft, "scope", provider, authorized=True)
    return provider


@pytest.mark.parametrize("field", ["role", "scope", "candidate_id", "company", "start_date"])
@pytest.mark.parametrize("value", ["", " ", None])
def test_required_metadata_before_write(repo, field, value):
    with pytest.raises(ValueError):
        start(repo, **{field: value})
    assert repo.get_company_draft("a") is None


def test_repository_requires_role_for_v4(repo):
    with pytest.raises(ValueError):
        repo.begin_company_interview(candidate_id="a", company="Synthetic", role="",
            start_date="2020-01", end_date=None, experience_id="bad", interview_version=V4_VERSION)


def test_exact_base_questions_and_zero_follow_up(repo):
    assert V4_QUESTIONS == (
        "Imagine I start tomorrow in your role. What would I actually be doing day to day?",
        "What kinds of problems were you responsible for solving, and what decisions could you make yourself?",
        "Can you give me an example of something you handled particularly well, improved, solved, or helped achieve in this role?",
    )
    draft = start(repo)
    for i, question in enumerate(V4_QUESTIONS, 1):
        assert current_question(draft) == (f"q{i}", question, "FIXED_QUESTION")
        confirm_text(draft, "scope", repo, f"Source {i}")
    assert draft["stage"] == "reflection_pending"
    reflect(draft)
    assert draft["stage"] == "review"
    finalize(draft, "scope", repo)
    assert draft["stage"] == "complete"
    item = repo.list_work_experiences("a")[0]
    assert item.role == "Analyst"
    assert len(item.confirmed_interview_answers) == 3


@pytest.mark.parametrize("second", [None, "evidence_contribution"])
def test_sequential_decisions_include_first_adaptive_and_cap_at_two(repo, second):
    draft = base(repo)
    reflect(draft, "tools_resources")
    assert current_question(draft)[1] == "What tools, systems or technologies did you use to do that?"
    provider = Mock()
    with pytest.raises(ValueError):
        reflect_v4(draft, "scope", provider, authorized=True)
    provider.generate.assert_not_called()
    confirm_text(draft, "scope", repo, "I used SQL for those checks.")
    assert draft["stage"] == "reflection_pending"
    assert repo.list_company_answers("a", draft["id"])[0].confirmed_text == "I used SQL for those checks."
    provider = reflect(draft, second)
    request = json.loads(provider.generate.call_args.args[0].split("SOURCE DATA:\n")[1])
    assert len(request["sources"]) == 4
    assert request["sources"][-1]["confirmed_text"] == "I used SQL for those checks."
    if second:
        assert current_question(draft)[0] == "adaptive_evidence_contribution"
        confirm_text(draft, "scope", repo, "I resolved the incident.")
    assert draft["stage"] == "review"
    assert len(draft["answers"]) == (5 if second else 4)
    with pytest.raises(ValueError):
        reflect_v4(draft, "scope", Mock(), authorized=True)
    with pytest.raises(ValueError):
        confirm_text(draft, "scope", repo, "Extra")
    finalize(draft, "scope", repo)


def test_repeat_dimension_and_legacy_batch_selector_rejected(repo):
    draft = base(repo)
    with pytest.raises(ValueError):
        set_adaptive_dimensions(draft, "scope", ["core_work", "tools_resources"])
    reflect(draft, "core_work")
    skip_question(draft, "scope", repo)
    before = copy.deepcopy(draft)
    with pytest.raises(ValueError, match="reflection_contract_invalid"):
        reflect(draft, "core_work")
    assert draft == before


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 5])
def test_durable_resume_from_only_confirmed_sources(repo, count):
    draft = start(repo)
    for i in range(min(count, 3)):
        confirm_text(draft, "scope", repo, f"Source {i}")
    for dim in ["core_work", "tools_resources"][:max(0, count-3)]:
        reflect(draft, dim)
        confirm_text(draft, "scope", repo, "Confirmed adaptive source")
    resumed = resume_interview("new-scope", "a", CandidateOnboardingRepository())
    assert resumed["role"] == "Analyst"
    assert resumed["reflection"] is None and resumed["adaptive_dimension"] is None
    assert len(resumed["answers"]) == count
    assert resumed["stage"] == ("question" if count < 3 else "review" if count == 5 else "reflection_pending")
    if count < 3:
        assert current_question(resumed)[0] == f"q{count+1}"
    assert resume_interview("other", "b", repo) is None


def test_skip_prompt_and_transient_coverage(repo):
    draft = start(repo)
    for _ in range(3):
        skip_question(draft, "scope", repo)
    request = reflection_request_v4(draft)
    assert set(request) == {"company", "role", "start_date", "end_date", "sources"}
    assert all(set(a) == {"question_id", "question_text", "confirmed_text", "skipped", "source_kind"}
               for a in request["sources"])
    assert all(a["skipped"] and a["confirmed_text"] == "" for a in request["sources"])
    prompt = build_reflection_prompt_v4(request)
    for text in ("Never interpret skip as absence", "UNKNOWN", "PARTIAL alone",
                 "tools did not already emerge", "context", "never evidence", "ALL confirmed"):
        assert text in prompt
    before = repo.list_company_answers("a", draft["id"])
    reflect(draft)
    assert repo.list_company_answers("a", draft["id"]) == before
    assert "reflection" not in repo.get_company_draft("a")


@pytest.mark.parametrize("status", ["SUFFICIENT", "PARTIAL", "INSUFFICIENT"])
def test_no_dimension_is_valid_at_any_coverage(repo, status):
    request = reflection_request_v4(base(repo))
    assert parse_reflection_v4(json.dumps(output(status=status)), request)["next_missing_dimension"] is None


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(interpretation={}),
    lambda d: d.update(question="Provider wording"),
    lambda d: d.update(next_missing_dimension=["core_work", "tools_resources"]),
    lambda d: d.update(next_missing_dimension="unknown"),
    lambda d: d.update(next_missing_dimension="core_work"),
    lambda d: d["coverage"].update(core_work="PARTIAL") or d.update(next_missing_dimension="core_work"),
    lambda d: d["coverage"].update(core_work=True),
    lambda d: d["coverage"].pop("tools_resources"),
])
def test_strict_coverage_output(repo, mutation):
    request = reflection_request_v4(base(repo))
    data = output()
    mutation(data)
    with pytest.raises(ValueError, match="reflection_contract_invalid"):
        parse_reflection_v4(json.dumps(data), request)


def test_provider_failure_and_unauthorized_calls_preserve_state(repo):
    draft = base(repo)
    before = copy.deepcopy(draft)
    provider = Mock()
    for scope, authorized in [("other", True), ("scope", False)]:
        with pytest.raises(ValueError):
            reflect_v4(draft, scope, provider, authorized=authorized)
    provider.generate.assert_not_called()
    provider.generate.side_effect = RuntimeError("offline failure")
    with pytest.raises(RuntimeError):
        reflect_v4(draft, "scope", provider, authorized=True)
    assert draft == before
    reflect(draft)  # Explicit retry, no automatic retry loop.


def test_voice_confirmation_discard_and_write_failure(repo, monkeypatch):
    import services.company_interview as module
    monkeypatch.setattr(module, "audio_duration", lambda _: 1)
    draft = start(repo)
    provider = Mock()
    provider.transcribe.return_value = SimpleNamespace(status="succeeded", transcript_text="Draft transcript")
    config = SimpleNamespace(transcription_enabled=True, model="fake")
    transcribe_voice(draft, "scope", b"audio", provider, config, authorized=True)
    assert repo.list_company_answers("a", draft["id"]) == []
    discard_voice(draft, "scope")
    assert repo.list_company_answers("a", draft["id"]) == []
    transcribe_voice(draft, "scope", b"audio", provider, config, authorized=True)
    failing = Mock()
    failing.save_company_answer.side_effect = RuntimeError("offline write failure")
    with pytest.raises(RuntimeError):
        confirm_voice_transcript(draft, "scope", failing, "Edited confirmed source")
    assert draft["stage"] == "voice_review"
    confirm_voice_transcript(draft, "scope", repo, "Edited confirmed source")
    saved = repo.list_company_answers("a", draft["id"])
    assert len(saved) == 1 and saved[0].confirmed_text == "Edited confirmed source"
    assert saved[0].answer_mode == "voice"
    assert draft["pending_voice"] is None
    assert current_question(draft)[0] == "q2"


def test_correction_and_scoped_finalization(repo):
    draft = base(repo)
    reflect(draft)
    save_correction(draft, "scope", repo, "My correction")
    save_correction(draft, "scope", repo, "Updated correction")
    assert sum(a.question_id == "correction" for a in draft["answers"]) == 1
    resumed = resume_interview("scope", "a", repo)
    assert resumed["stage"] == "reflection_pending"
    assert any(a["confirmed_text"] == "Updated correction" for a in reflection_request_v4(resumed)["sources"])
    with pytest.raises(ValueError):
        repo.finalize_company_interview(candidate_id="b", experience_id=draft["id"])
    finalize(draft, "scope", repo)
    assert repo.list_work_experiences("b") == []


def adaptive(dimension):
    return ConfirmedCompanyAnswer("adaptive_"+dimension, V4_ADAPTIVE_QUESTIONS[dimension],
        "text", "Source", False, V4_VERSION, V4_VERSION, "ADAPTIVE_QUESTION")


def test_completion_validation_and_repository_cap(repo):
    draft = base(repo)
    answers = draft["answers"]
    validate_answers(answers)
    invalid = [
        answers[:2], answers + [answers[0]],
        answers + [adaptive(d) for d in list(V4_ADAPTIVE_QUESTIONS)[:3]],
        answers + [adaptive("core_work"), adaptive("core_work")],
        answers + [replace(adaptive("core_work"), question_id="adaptive_unknown")],
        [replace(answers[0], question_text="Wrong")] + answers[1:],
        [replace(answers[0], source_kind="ADAPTIVE_QUESTION")] + answers[1:],
        [replace(answers[0], interview_version=V3_VERSION)] + answers[1:],
    ]
    for collection in invalid:
        with pytest.raises(ValueError):
            validate_answers(collection)
    for dim in ["core_work", "tools_resources"]:
        repo.save_company_answer(candidate_id="a", experience_id=draft["id"], answer=adaptive(dim))
    with pytest.raises(ValueError):
        repo.save_company_answer(candidate_id="a", experience_id=draft["id"],
                                 answer=adaptive("evidence_contribution"))
    assert len(repo.list_company_answers("a", draft["id"])) == 5


def test_text_write_failure_does_not_advance(repo):
    draft = start(repo)
    before = copy.deepcopy(draft)
    failing = Mock()
    failing.save_company_answer.side_effect = RuntimeError("offline failure")
    with pytest.raises(RuntimeError):
        confirm_text(draft, "scope", failing, "Source")
    assert draft == before


def test_no_reflection_before_base_and_no_cross_version_sources(repo):
    draft = start(repo)
    provider = Mock()
    with pytest.raises(ValueError):
        reflect_v4(draft, "scope", provider, authorized=True)
    provider.generate.assert_not_called()
    draft = base(repo)
    draft["answers"][0] = replace(draft["answers"][0], question_version=V3_VERSION)
    with pytest.raises(ValueError):
        reflection_request_v4(draft)


def test_duplicate_json_fields_are_rejected(repo):
    request = reflection_request_v4(base(repo))
    raw = json.dumps(output()).replace('"next_missing_dimension": null',
        '"next_missing_dimension": null, "next_missing_dimension": null')
    with pytest.raises(ValueError, match="reflection_contract_invalid"):
        parse_reflection_v4(raw, request)
