import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call
import traceback

import pytest

from models.candidate_onboarding import CandidateOnboarding
from models.company_interview import ConfirmedCompanyAnswer, V4_VERSION
from models.work_experience import WorkExperience
from models.onboarding_records import OnboardingEducationRecord, OnboardingCertificationRecord
from models.candidate_past import ProfessionalFact
from models.candidate_present import CandidateSkill, ProfessionalFactRef
from models.candidate_future import CandidateFuture
from models.candidate_priorities import CandidatePriorities, Priority, PriorityEffect
from models.professional_ontology import Skill, SkillLevel
from models.interpretation_boundary import InterpretationResponse
from services import professional_facts_operation as facts
from services import candidate_skills_operation as skills
from services import candidate_priorities_operation as priorities
from services.candidate_profile_generator import ProfileGenerator, ProfileGenerationError


class Interpreter:
    def __init__(self, operation, build_output, history):
        self.operation = operation
        self.build_output = build_output
        self.history = history
        self.requests = []

    def interpret(self, request):
        if request.operation != self.operation:
            raise ValueError("Wrong operation for this interpreter")
        self.requests.append(request)
        self.history.append(request)
        output = self.build_output(request.input_payload)
        return InterpretationResponse(request.operation, request.input_signature, output)


def interpreters(empty_facts=False):
    history = []
    def fact_output(payload):
        return facts.ProfessionalFactsOutput(tuple(
            ProfessionalFact(facts.professional_fact_id(item.id, item.original_text),
                             item.original_text, item.id)
            for item in payload.inputs
        ) if not empty_facts else ())
    def skill_output(payload):
        return skills.CandidateSkillsOutput((CandidateSkill(
            Skill(skills.normalized_skill_id("SQL"), "SQL", "Data"), SkillLevel.UNKNOWN,
            tuple(ProfessionalFactRef(f.id) for f in payload.facts),
        ),))
    def priority_output(payload):
        return CandidatePriorities((Priority(
            priorities.priority_id("work_mode", "equals", "Remote", PriorityEffect.PREFER),
            "work_mode", "equals", "Remote", PriorityEffect.PREFER,
        ),))
    return SimpleNamespace(
        facts_interpreter=Interpreter(facts.OPERATION, fact_output, history),
        skills_interpreter=Interpreter(skills.OPERATION, skill_output, history),
        priorities_interpreter=Interpreter(priorities.OPERATION, priority_output, history),
        requests=history,
    )


def answer(qid="q1", text="  I used SQL.\nExact source.  ", skipped=False):
    return ConfirmedCompanyAnswer(qid, "Question is not evidence", "skip" if skipped else "text",
                                  text, skipped, V4_VERSION, V4_VERSION)


def experience(id="exp", **changes):
    return replace(WorkExperience(id, "a", "Company", "2020-01", None,
        "Legacy story", "Legacy projection", [answer()], "Analyst"), **changes)


@pytest.fixture
def sources():
    source = Mock(spec=["get_onboarding", "list_work_experiences", "list_education", "list_certifications"])
    source.get_onboarding.return_value = CandidateOnboarding(
        "a", country=" Ireland ", city=" Dublin ", spoken_languages=["Portuguese", "English"],
        priority_declaration=" I prefer remote work. ",
        location="Legacy location", work_authorisation="Legacy authorization",
        desired_next_work="Legacy direction", enjoyed_work="Legacy enjoyment",
        avoid_work="Legacy avoidance", development_interests="Legacy development",
        career_priorities=["Legacy priority"],
    )
    source.list_work_experiences.return_value = [experience(), experience("second", confirmed_interview_answers=[
        answer(text="I checked a report."), answer("q2", "", True), answer("q3", "   "),
    ])]
    source.list_education.return_value = [OnboardingEducationRecord("ed", "a", "School", "Diploma", "Data")]
    source.list_certifications.return_value = [OnboardingCertificationRecord("cert", "a", "Certificate", "Issuer", 2020)]
    return source


def generate(sources, interpreter=None):
    dependencies = interpreter or interpreters()
    return ProfileGenerator(onboarding_repository=sources,
        facts_interpreter=dependencies.facts_interpreter,
        skills_interpreter=dependencies.skills_interpreter,
        priorities_interpreter=dependencies.priorities_interpreter).generate("a")


def test_complete_raw_becomes_unpersisted_v1_with_exact_source_branches(sources):
    interpreter = interpreters()
    before = deepcopy([method.return_value for method in (
        sources.get_onboarding, sources.list_work_experiences, sources.list_education, sources.list_certifications)])
    result = generate(sources, interpreter)
    assert (result.candidate_id, result.version, result.future) == ("a", 1, CandidateFuture())
    assert (result.present.country, result.present.city, result.present.languages) == (
        " Ireland ", " Dublin ", ("Portuguese", "English"))
    for raw, entity in zip(sources.list_work_experiences.return_value, result.past.experiences):
        assert (entity.id, entity.company, entity.role, entity.start_date, entity.end_date) == (
            raw.id, raw.company, raw.role, raw.start_date, raw.end_date)
        expected = [a.confirmed_text for a in raw.confirmed_interview_answers if not a.skipped and a.confirmed_text.strip()]
        assert [item.original_text for item in entity.inputs] == expected
        assert {fact.candidate_input_id for fact in entity.facts} <= {item.id for item in entity.inputs}
    ed = result.past.education[0]
    assert (ed.id, ed.institution, ed.qualification, ed.field) == ("ed", "School", "Diploma", "Data")
    assert (ed.start_date, ed.end_date, ed.status, ed.inputs, ed.facts) == (None, None, None, (), ())
    cert = result.past.certifications[0]
    assert (cert.id, cert.name, cert.issuer, cert.issued_at, cert.expires_at, cert.status) == (
        "cert", "Certificate", "Issuer", "2020", None, None)
    assert result.present.skills[0].level is SkillLevel.UNKNOWN
    assert result.priorities.priorities[0].effect is PriorityEffect.PREFER
    assert before == [method.return_value for method in (
        sources.get_onboarding, sources.list_work_experiences, sources.list_education, sources.list_certifications)]
    assert sources.mock_calls == [call.get_onboarding("a"), call.list_work_experiences("a"),
                                  call.list_education("a"), call.list_certifications("a")]


def test_facts_are_per_experience_then_skills_receive_all_facts_once(sources):
    interpreter = interpreters()
    result = generate(sources, interpreter)
    assert [r.operation for r in interpreter.requests] == [facts.OPERATION, facts.OPERATION, skills.OPERATION, priorities.OPERATION]
    assert interpreter.facts_interpreter.requests == interpreter.requests[:2]
    assert interpreter.skills_interpreter.requests == interpreter.requests[2:3]
    assert interpreter.priorities_interpreter.requests == interpreter.requests[3:]
    for entity, request in zip(result.past.experiences, interpreter.requests):
        assert request.input_payload.inputs == entity.inputs
    all_facts = tuple(f for entity in result.past.experiences for f in entity.facts)
    assert interpreter.requests[2].input_payload.facts == all_facts
    assert {ref.fact_id for skill in result.present.skills for ref in skill.evidence_refs} == {f.id for f in all_facts}
    declaration = interpreter.requests[3].input_payload.declarations[0]
    assert declaration.text == sources.get_onboarding.return_value.priority_declaration


@pytest.mark.parametrize("bound_name,wrong_operation", [
    ("facts", skills.OPERATION), ("facts", priorities.OPERATION),
    ("skills", facts.OPERATION), ("skills", priorities.OPERATION),
    ("priorities", facts.OPERATION), ("priorities", skills.OPERATION),
])
def test_each_fake_rejects_other_operations(sources, bound_name, wrong_operation):
    dependencies = interpreters()
    generate(sources, dependencies)
    wrong_request = next(r for r in dependencies.requests if r.operation == wrong_operation)
    bound = getattr(dependencies, bound_name + "_interpreter")
    before = list(bound.requests)
    with pytest.raises(ValueError, match="Wrong operation"):
        bound.interpret(wrong_request)
    assert bound.requests == before


@pytest.mark.parametrize("stage,wrong", [("facts", "skills"), ("skills", "priorities"), ("priorities", "facts")])
def test_wrong_composition_fails_at_bound_operation(sources, stage, wrong):
    dependencies = interpreters()
    setattr(dependencies, stage + "_interpreter", getattr(dependencies, wrong + "_interpreter"))
    with pytest.raises(ProfileGenerationError) as error:
        generate(sources, dependencies)
    assert error.value.stage == stage


def test_repeated_generation_equal_and_source_ids_stable_not_content_owned(sources):
    first, second = generate(sources), generate(sources)
    assert first == second
    ids = [item.id for exp in first.past.experiences for item in exp.inputs]
    assert len(set(ids)) == len(ids)  # Both experiences have q1.
    sources.list_work_experiences.return_value[0].confirmed_interview_answers[0] = answer(text="Changed source")
    updated = generate(sources)
    assert updated.past.experiences[0].inputs[0].id == ids[0]
    assert updated.past.experiences[0].inputs[0].original_text == "Changed source"


@pytest.mark.parametrize("country,city", [("", ""), ("  ", "\t")])
def test_blank_about_has_no_legacy_fallback(sources, country, city):
    sources.get_onboarding.return_value = replace(sources.get_onboarding.return_value, country=country, city=city)
    result = generate(sources)
    assert result.present.country is None and result.present.city is None
    assert result.future == CandidateFuture()


@pytest.mark.parametrize("legacy_field", [
    "location", "work_authorisation", "desired_next_work", "enjoyed_work",
    "avoid_work", "development_interests", "career_priorities",
])
def test_legacy_fields_have_no_influence(sources, legacy_field):
    baseline = generate(sources)
    setattr(sources.get_onboarding.return_value, legacy_field, ["Different"] if legacy_field == "career_priorities" else "Different")
    assert generate(sources) == baseline


@pytest.mark.parametrize("answers", [[], [answer(skipped=True)], [answer(text="")], [answer(text="  ")]])
def test_no_usable_answers_preserves_experience_without_interpretation(sources, answers):
    sources.list_work_experiences.return_value = [experience(confirmed_interview_answers=answers)]
    sources.get_onboarding.return_value.priority_declaration = "  "
    interpreter = interpreters()
    result = generate(sources, interpreter)
    assert result.past.experiences[0].inputs == result.past.experiences[0].facts == ()
    assert result.present.skills == ()
    assert result.priorities == CandidatePriorities()
    assert interpreter.requests == []


def test_valid_empty_fact_response_does_not_call_skills(sources):
    interpreter = interpreters(empty_facts=True)
    result = generate(sources, interpreter)
    assert result.present.skills == ()
    assert skills.OPERATION not in [r.operation for r in interpreter.requests]
    assert interpreter.skills_interpreter.requests == []


@pytest.mark.parametrize("text", ["", " \n\t"])
def test_blank_priorities_does_not_call_interpreter_or_use_legacy_priorities(sources, text):
    sources.get_onboarding.return_value.priority_declaration = text
    interpreter = interpreters()
    assert generate(sources, interpreter).priorities == CandidatePriorities()
    assert priorities.OPERATION not in [r.operation for r in interpreter.requests]
    assert interpreter.priorities_interpreter.requests == []


@pytest.mark.parametrize("operation,stage", [
    (facts.OPERATION, "facts"), (skills.OPERATION, "skills"), (priorities.OPERATION, "priorities"),
])
@pytest.mark.parametrize("failure", ["provider", "binding", "provenance"])
def test_necessary_interpretation_failure_stops_safely(sources, operation, stage, failure):
    interpreter = interpreters()
    bound = getattr(interpreter, stage + "_interpreter")
    original = bound.interpret
    def interpret(request):
        assert request.operation == operation
        if failure == "provider":
            raise RuntimeError("private payload and provider secret")
        response = original(request)
        if failure == "binding":
            return replace(response, input_signature="wrong")
        if operation == facts.OPERATION:
            output = facts.ProfessionalFactsOutput((ProfessionalFact("AI-owned", "Wrong", "foreign"),))
        elif operation == skills.OPERATION:
            item = response.output_payload.skills[0]
            output = skills.CandidateSkillsOutput((replace(item, evidence_refs=(ProfessionalFactRef("foreign"),)),))
        else:
            output = CandidatePriorities((replace(response.output_payload.priorities[0], id="AI-owned"),))
        return replace(response, output_payload=output)
    bound.interpret = interpret
    before = deepcopy(sources.get_onboarding.return_value)
    with pytest.raises(ProfileGenerationError) as error:
        generate(sources, interpreter)
    assert error.value.stage == stage
    assert "private payload" not in "".join(traceback.format_exception(error.value))
    assert sources.get_onboarding.return_value == before
    order = [facts.OPERATION, skills.OPERATION, priorities.OPERATION]
    assert all(order.index(r.operation) <= order.index(operation) for r in interpreter.requests)


@pytest.mark.parametrize("method", ["get_onboarding", "list_work_experiences", "list_education", "list_certifications"])
def test_foreign_candidate_sources_fail_before_interpretation(sources, method):
    target = getattr(sources, method).return_value
    if isinstance(target, list):
        target[0] = replace(target[0], candidate_id="foreign")
    else:
        getattr(sources, method).return_value = replace(target, candidate_id="foreign")
    interpreter = interpreters()
    with pytest.raises(ProfileGenerationError, match="source"):
        generate(sources, interpreter)
    assert not interpreter.requests


def test_missing_raw_is_not_silently_fabricated(sources):
    sources.get_onboarding.return_value = None
    with pytest.raises(ProfileGenerationError, match="source"):
        generate(sources)


@pytest.mark.parametrize("version", ["company-interview-v1", "company-interview-v2", "company-interview-v3"])
def test_historical_interview_answers_are_not_silently_converted_to_v4(sources, version):
    sources.list_work_experiences.return_value[0].confirmed_interview_answers[0] = replace(
        answer(), interview_version=version, question_version=version)
    interpreter = interpreters()
    with pytest.raises(ProfileGenerationError, match="source"):
        generate(sources, interpreter)
    assert not interpreter.requests


def test_duplicate_source_identity_rejected_before_ai(sources):
    source = sources.list_work_experiences.return_value[0]
    source.confirmed_interview_answers.append(answer())
    interpreter = interpreters()
    with pytest.raises(ProfileGenerationError, match="source"):
        generate(sources, interpreter)
    assert not interpreter.requests


def test_generator_has_only_source_and_interpretation_dependencies():
    import services.candidate_profile_generator as module
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == {
        "dataclasses", "typing", "models.candidate_past", "models.candidate_present",
        "models.candidate_future", "models.candidate_priorities", "models.candidate_profile_snapshot",
        "models.interpretation_boundary", "models.company_interview", "services", "services.candidate_onboarding_repository",
    }
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"execute", "save_candidate", "current_candidate", "create_initial_profile", "update", "generate"}


def test_actual_confirmed_repository_boundary_excludes_drafts_and_does_not_persist_profile():
    from models.candidate import Candidate
    from models.company_interview import V4_QUESTIONS
    from services.candidate_repository import CandidateRepository
    from services.candidate_onboarding_repository import CandidateOnboardingRepository
    from services.candidate_profile_repository import CandidateProfileRepository
    CandidateRepository().save(Candidate("a", "Synthetic", "", "", ""))
    repo = CandidateOnboardingRepository()
    repo.save_onboarding(CandidateOnboarding("a", country="Ireland", city="Dublin", spoken_languages=["English"]))
    answers = [ConfirmedCompanyAnswer(f"q{index}", text, "text", f"Exact source {index}", False, V4_VERSION, V4_VERSION)
               for index, text in enumerate(V4_QUESTIONS, 1)]
    repo.confirm_company_interview(candidate_id="a", company="Company", role="Analyst",
        start_date="2020-01", end_date=None, experience_id="confirmed", answers=answers)
    repo.begin_company_interview(candidate_id="a", company="Draft", role="Role",
        start_date="2021-01", end_date=None, experience_id="draft", interview_version=V4_VERSION)
    original = deepcopy(repo.list_work_experiences("a"))
    result = generate(repo)
    assert [exp.id for exp in result.past.experiences] == ["confirmed"]
    assert repo.list_work_experiences("a") == original
    assert repo.get_company_draft("a") is not None
    assert CandidateProfileRepository().current_candidate("a") is None
