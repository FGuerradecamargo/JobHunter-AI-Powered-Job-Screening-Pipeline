from dataclasses import asdict, replace
from pathlib import Path

import pytest

from models.application_context import PositioningTheme
from models.application_contract import ApplicationEvidenceRef
from models.interview_context import InterviewContext
from services.interview_preparation_builder import build_interview_preparation
from services.interview_preparation_service import InterviewPreparationService


def _evidence(ref, statement, authority="professional_fact"):
    return ApplicationEvidenceRef(
        evidence_ref=ref,
        source_type="professional_experience",
        source_id="experience-1",
        authority=authority,
        statement=statement,
    )


def _context(**changes):
    values = dict(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        interview_prep_contract_signature="prep-signature",
        interview_stage="interview",
        job_title="Product Operations Specialist",
        company="Example Ltd",
        role_family="Product Operations",
        job_level="Specialist",
        interview_type="",
        interview_format="",
        interviewer="",
        duration_minutes=None,
        scheduled_at="",
        instructions="",
        explicit_topics=["SQL", "Commercial awareness"],
        core_requirements=["Stakeholder management", "Process improvement"],
        authorized_evidence=[
            _evidence("e-stakeholder", "Stakeholder management"),
            _evidence("e-sql", "SQL", "developing_evidence"),
        ],
        positioning_themes=[
            PositioningTheme("Stakeholder leadership", ["e-stakeholder"]),
            PositioningTheme("Unsupported theme", ["missing-ref"]),
        ],
        development_gaps=["Advanced SQL"],
        structural_gaps=["No production Kubernetes experience"],
        source_signature="interview-context-signature",
    )
    values.update(changes)
    return InterviewContext(**values)


def _areas(preparation, source_type):
    return [area for area in preparation.preparation_areas if area.source_type == source_type]


def test_builds_preparation_for_eligible_interview_context():
    result = build_interview_preparation(_context())
    assert result.interview_stage == "interview"
    assert result.preparation_areas
    assert result.authority == "derived_interview_guidance"


def test_candidate_job_and_analysis_identity_are_preserved():
    result = build_interview_preparation(_context())
    assert (result.candidate_id, result.job_id, result.analysis_id) == (
        "candidate-a", "job-1", "analysis-1"
    )


def test_each_core_requirement_creates_a_preparation_area():
    result = build_interview_preparation(_context())
    assert {area.topic for area in _areas(result, "core_requirement")} == {
        "Stakeholder management", "Process improvement"
    }


def test_explicit_topic_has_explicit_priority_without_becoming_evidence():
    result = build_interview_preparation(_context())
    commercial = next(area for area in result.preparation_areas if area.topic == "Commercial awareness")
    assert commercial.source_type == "explicit_interview_topic"
    assert commercial.priority == "explicit"
    assert commercial.evidence_refs == []
    assert "No authorized evidence" in commercial.caution


def test_exact_normalized_matching_carries_authorized_evidence_refs():
    result = build_interview_preparation(_context())
    stakeholder = next(
        area for area in _areas(result, "core_requirement")
        if area.topic == "Stakeholder management"
    )
    assert stakeholder.evidence_refs == ["e-stakeholder"]
    assert stakeholder.priority == "high"


def test_non_exact_keyword_overlap_is_not_treated_as_proof():
    context = _context(
        core_requirements=["Advanced stakeholder management"],
        authorized_evidence=[_evidence("e-1", "Stakeholder management")],
        positioning_themes=[],
    )
    area = _areas(build_interview_preparation(context), "core_requirement")[0]
    assert area.evidence_refs == []
    assert "do not imply" in area.caution


def test_developing_evidence_remains_developing():
    sql = next(area for area in build_interview_preparation(_context()).preparation_areas if area.topic == "SQL")
    assert sql.evidence_refs == ["e-sql"]
    assert sql.gap_type == "developing_evidence"
    assert "do not present it as proven expertise" in sql.caution


def test_structural_gap_explicitly_prevents_overclaiming():
    area = _areas(build_interview_preparation(_context()), "structural_gap")[0]
    assert area.priority == "high"
    assert area.gap_type == "structural"
    assert "Do not imply experience" in area.caution
    assert area.evidence_refs == []


def test_development_gap_uses_honest_current_level_framing():
    area = _areas(build_interview_preparation(_context()), "development_gap")[0]
    assert area.priority == "high"
    assert "current level accurately" in area.what_to_demonstrate
    assert "developing capability" in area.caution


def test_positioning_theme_requires_valid_authorized_evidence_ref():
    areas = _areas(build_interview_preparation(_context()), "positioning_theme")
    assert [(area.topic, area.evidence_refs) for area in areas] == [
        ("Stakeholder leadership", ["e-stakeholder"])
    ]


def test_theme_keeps_only_valid_refs_and_never_fails_open():
    context = _context(
        positioning_themes=[PositioningTheme("Theme", ["missing", "e-stakeholder"])]
    )
    area = _areas(build_interview_preparation(context), "positioning_theme")[0]
    assert area.evidence_refs == ["e-stakeholder"]


def test_final_interview_has_distinct_deterministic_framing():
    interview = build_interview_preparation(_context())
    final = build_interview_preparation(_context(interview_stage="final_interview"))
    assert interview.summary_guidance != final.summary_guidance
    assert "ownership, impact, tradeoffs" in final.summary_guidance
    assert interview.source_signature != final.source_signature


def test_recruiter_instructions_are_preserved_verbatim():
    instructions = "Prepare a case study.\nDo not disclose client data."
    result = build_interview_preparation(_context(instructions=instructions))
    assert result.interview_instructions[0] == instructions


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("interview_format", "Panel", "supplied interview format: Panel"),
        ("interview_type", "Case study", "supplied interview type: Case study"),
        ("interviewer", "Morgan, Hiring Manager", "Interviewer information supplied"),
        ("duration_minutes", 30, "supplied duration is 30 minutes"),
    ],
)
def test_interview_details_influence_guidance_only_when_supplied(field, value, expected):
    baseline = build_interview_preparation(_context())
    changed = build_interview_preparation(_context(**{field: value}))
    assert not any(expected in item for item in baseline.interview_instructions)
    assert any(expected in item for item in changed.interview_instructions)


def test_questions_are_generic_and_opportunity_grounded():
    questions = build_interview_preparation(_context()).questions_to_ask_the_company
    assert "Product Operations Specialist" in questions[0]
    assert any("teams and stakeholders" in item for item in questions)
    assert not any("Example Ltd has" in item for item in questions)


def test_rehearsal_prompts_are_not_predictions_or_scripted_answers():
    prompts = build_interview_preparation(_context()).rehearsal_prompts
    assert prompts
    assert all(item.startswith("Prepare to discuss") for item in prompts)
    assert all("They will ask" not in item for item in prompts)


def test_output_contains_no_invented_first_person_candidate_story():
    output = str(asdict(build_interview_preparation(_context())))
    assert "When I worked" not in output
    assert "I successfully" not in output
    assert "my experience" not in output.casefold()
    assert "five stakeholders" not in output.casefold()


def test_same_context_produces_same_object_and_signature():
    first = build_interview_preparation(_context())
    second = build_interview_preparation(_context())
    assert first == second
    assert first.source_signature == second.source_signature


@pytest.mark.parametrize(
    "change",
    [
        {"interview_stage": "final_interview"},
        {"core_requirements": ["Commercial strategy"]},
        {"explicit_topics": ["Python"]},
        {"instructions": "Prepare a presentation"},
        {"development_gaps": ["Negotiation"]},
        {"structural_gaps": ["No regulated-industry experience"]},
        {"authorized_evidence": [_evidence("e-new", "Commercial strategy")]},
    ],
)
def test_material_context_change_changes_signature(change):
    baseline = build_interview_preparation(_context())
    changed = build_interview_preparation(_context(**change))
    assert baseline.source_signature != changed.source_signature


def test_ordering_whitespace_and_case_noise_do_not_change_signature():
    context = _context()
    noisy = replace(
        context,
        core_requirements=[" process   IMPROVEMENT ", " STAKEHOLDER management "],
        explicit_topics=[" commercial awareness ", " sql "],
        development_gaps=[" advanced   sql "],
        structural_gaps=[" no PRODUCTION kubernetes experience "],
        authorized_evidence=list(reversed(context.authorized_evidence)),
        positioning_themes=list(reversed(context.positioning_themes)),
    )
    assert (
        build_interview_preparation(context).source_signature
        == build_interview_preparation(noisy).source_signature
    )


class ContextService:
    def __init__(self, context):
        self.context = context
        self.calls = []

    def build(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return self.context

    def save(self, *_args, **_kwargs):
        raise AssertionError("Preparation read path must not write.")


def test_service_builds_context_once_and_performs_no_writes():
    context_service = ContextService(_context())
    result = InterviewPreparationService(context_service=context_service).build(
        "candidate-a", "job-1"
    )
    assert result.candidate_id == "candidate-a"
    assert context_service.calls == [("candidate-a", "job-1")]


@pytest.mark.parametrize(
    "context,error",
    [
        (_context(candidate_id="candidate-b"), "another candidate"),
        (_context(job_id="job-2"), "another job"),
    ],
)
def test_service_scope_mismatch_fails_closed(context, error):
    service = InterviewPreparationService(context_service=ContextService(context))
    with pytest.raises(PermissionError, match=error):
        service.build("candidate-a", "job-1")


def test_inactive_or_incomplete_context_fails_closed():
    with pytest.raises(ValueError, match="active interview"):
        build_interview_preparation(_context(interview_stage="applied"))
    with pytest.raises(ValueError, match="incomplete"):
        build_interview_preparation(_context(source_signature=""))


def test_preparation_engine_has_no_ai_api_or_generator_path():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "models/interview_preparation.py",
            "services/interview_preparation_builder.py",
            "services/interview_preparation_service.py",
        )
    ).lower()
    assert "openai" not in source
    assert "llm" not in source
    assert ".generate(" not in source
    assert "requests." not in source
