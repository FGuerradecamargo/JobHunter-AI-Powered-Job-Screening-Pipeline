from dataclasses import asdict, fields, replace
import pytest

from models.application_tracking import InterviewRound, InterviewRoundFeedback
from models.company_profile import CompanyPublicSource, CompanyClaim, CompanyProfileDraft
from models.interview_brief import InterviewerPublicContext
from models.interview_preparation import InterviewPreparation, PreparationArea
from services.company_profile_builder import build_company_profile
from services.interview_brief_builder import build_interview_brief


def preparation():
    return InterviewPreparation(candidate_id="c", job_id="j", analysis_id="a", interview_context_signature="ctx",
        interview_stage="interview", summary_guidance="Use truthful examples", source_signature="prep",
        preparation_areas=[PreparationArea(topic="SQL", source_type="core_requirement", priority="core",
            what_they_seek="SQL", what_to_demonstrate="Explain source evidence", example_direction="Actual example", evidence_refs=["e1"])])


def round(n=1):
    return InterviewRound(f"i{n}", "c", "j", n, "", interviewer_roles=("Technical lead",))


def company():
    return build_company_profile(company_id="company", sources=(CompanyPublicSource(ref="web:company", source_type="company_website",
        company_id="company", summary="Builds software."),), draft=CompanyProfileDraft(what_they_do="Builds software.",
        claims=(CompanyClaim("what_they_do", "Builds software.", "web:company"),), uncertainties=("Size unknown",)),
        created_at="2026-09-26T00:00:00+00:00")


def test_company_context_keeps_attribution_signature_uncertainty_and_inputs():
    p, c = preparation(), company()
    before = asdict(p), asdict(c)
    brief = build_interview_brief(preparation=p, interview_round=round(), company_profile=c, expected_company_id="company")
    assert brief.company_context == ("Builds software.",)
    assert brief.company_claims[0].attribution == "source_reported"
    assert brief.company_claims[0].source_ref == "web:company"
    assert brief.company_source_signature == c.source_signature
    assert brief.company_uncertainties == ("Size unknown",)
    assert (asdict(p), asdict(c)) == before
    assert brief.source_signature == build_interview_brief(preparation=p, interview_round=round(), company_profile=c, expected_company_id="company").source_signature


def test_unknown_company_and_interviewer_stay_unknown():
    brief = build_interview_brief(preparation=preparation(), interview_round=round())
    assert brief.company_context == () and brief.company_profile_version is None
    assert brief.interviewer_contexts == ()
    role = InterviewerPublicContext(role="Technical lead")
    assert role.name == ""
    assert build_interview_brief(preparation=preparation(), interview_round=round(), interviewer_contexts=(role,)).interviewer_contexts == (role,)


@pytest.mark.parametrize("ref", ["gmail:x", "GMAIL:x", "user:x", "private:x", "manual:x"])
def test_private_interviewer_sources_rejected(ref):
    with pytest.raises(ValueError):
        InterviewerPublicContext(role="Technical lead", source_refs=(ref,))


def test_professional_research_requires_provenance_and_no_personal_fields():
    with pytest.raises(ValueError):
        InterviewerPublicContext(role="Technical lead", professional_background=("Invented trajectory",))
    assert not {"politics", "health", "family", "hobbies", "personality"} & {f.name for f in fields(InterviewerPublicContext)}
    person = InterviewerPublicContext(role="Technical lead", current_role="Technical lead", source_refs=("https://company.example/team",))
    assert build_interview_brief(preparation=preparation(), interview_round=round(), interviewer_contexts=(person,)).interviewer_contexts == (person,)


def test_cross_company_and_cross_candidate_rejected():
    with pytest.raises(PermissionError):
        build_interview_brief(preparation=preparation(), interview_round=round(), company_profile=company(), expected_company_id="other")
    with pytest.raises(PermissionError):
        build_interview_brief(preparation=replace(preparation(), candidate_id="other"), interview_round=round())
    with pytest.raises(ValueError):
        build_interview_brief(preparation=preparation(), interview_round=round(), interviewer_contexts=(InterviewerPublicContext(name="Unrelated"),))


def test_only_verified_previous_round_feedback_is_used():
    feedback = InterviewRoundFeedback("i1", "c", "j", "Discussed SQL", "Bring an example")
    brief = build_interview_brief(preparation=preparation(), interview_round=round(2), previous_rounds=(round(),), previous_feedback=(feedback,))
    assert brief.previous_round_feedback == ("Discussed SQL",)
    assert brief.next_stage_context == ("Bring an example",)
    assert brief.previous_round_refs == ("i1",)
    assert not hasattr(brief, "candidate_profile_update")
    for invalid in (replace(feedback, interview_id="i3"), replace(feedback, interview_id="i2")):
        with pytest.raises(ValueError):
            build_interview_brief(preparation=preparation(), interview_round=round(2), previous_rounds=(round(), round(2), round(3)), previous_feedback=(invalid,))
    with pytest.raises(PermissionError):
        build_interview_brief(preparation=preparation(), interview_round=round(2), previous_feedback=(replace(feedback, candidate_id="other"),))


def test_developing_evidence_keeps_caution_and_is_not_strongest():
    p = preparation()
    p.preparation_areas.append(replace(p.preparation_areas[0], topic="Learning", gap_type="developing_evidence", caution="Not proven expertise"))
    brief = build_interview_brief(preparation=p, interview_round=round())
    assert [area.topic for area in brief.strongest_evidence] == ["SQL"]
    assert brief.likely_areas[1].caution == "Not proven expertise"


def test_feedback_changes_invalidate_brief_signature():
    args = dict(preparation=preparation(), interview_round=round(2), previous_rounds=(round(),))
    feedback = InterviewRoundFeedback("i1", "c", "j", "First")
    one = build_interview_brief(**args, previous_feedback=(feedback,))
    two = build_interview_brief(**args, previous_feedback=(replace(feedback, feedback_text="Second"),))
    assert one.source_signature != two.source_signature


def test_feedback_order_uses_round_sequence_not_write_timestamp():
    first = InterviewRoundFeedback("i1", "c", "j", "First round", created_at="later edit")
    second = InterviewRoundFeedback("i2", "c", "j", "Second round", created_at="earlier write")
    brief = build_interview_brief(preparation=preparation(), interview_round=round(3),
        previous_rounds=(round(2), round()), previous_feedback=(second, first))
    assert brief.previous_round_feedback == ("First round", "Second round")
    assert brief.previous_round_refs == ("i1", "i2")
