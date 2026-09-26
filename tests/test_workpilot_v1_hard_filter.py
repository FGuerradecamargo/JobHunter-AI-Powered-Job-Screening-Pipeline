from models.candidate_profile import CandidateProfile
from models.job import Job
from models.job_profile import JobProfile
from services.analyzers.hard_filter_analyzer import HardFilterAnalyzer


def analyze(text, *, constraints=(), profile=None, job_profile=None):
    candidate = profile or CandidateProfile(
        hard_constraints=list(constraints),
    )
    job = Job(
        id="job-1",
        raw_text=text,
        url="https://example.test/job-1",
        title="Role",
        description=text,
    )
    return HardFilterAnalyzer(candidate).analyze(
        job,
        job_profile or JobProfile(job_id=job.id),
    )


def test_direction_mismatch_is_not_a_hard_filter():
    candidate = CandidateProfile(
        career_objective_title="Operations Analyst",
        target_roles=["Operations Analyst"],
    )
    result = analyze(
        "Software Engineering role building internal services.",
        profile=candidate,
        job_profile=JobProfile(
            job_id="job-1",
            canonical_role="Software Engineer",
            role_family="Software Engineering",
        ),
    )
    assert result["rejected"] is False


def test_seniority_is_not_a_hard_filter():
    candidate = CandidateProfile(current_level="specialist")
    result = analyze(
        "Director of Operations.",
        profile=candidate,
        job_profile=JobProfile(
            job_id="job-1",
            canonical_role="Director of Operations",
            seniority="director",
        ),
    )
    assert result["rejected"] is False


def test_language_missing_from_legacy_profile_is_not_confirmed_absence():
    candidate = CandidateProfile(spoken_languages=["English"])
    result = analyze(
        "Fluent German required.",
        profile=candidate,
    )
    assert result["rejected"] is False


def test_negated_night_shift_does_not_reject():
    result = analyze(
        "This is a day role. No night shifts required.",
        constraints=("no night work",),
    )
    assert result["rejected"] is False


def test_explicit_night_shift_and_candidate_constraint_rejects():
    result = analyze(
        "The role includes a rotating night shift.",
        constraints=("no night work",),
    )
    assert result["rejected"] is True
    assert any("night" in reason.lower() for reason in result["reasons"])


def test_negated_on_call_does_not_reject():
    result = analyze(
        "No overnight on-call is required for this position.",
        constraints=("no on-call",),
    )
    assert result["rejected"] is False


def test_explicit_overnight_on_call_and_constraint_rejects():
    result = analyze(
        "Engineers participate in overnight on-call.",
        constraints=("no on-call",),
    )
    assert result["rejected"] is True


def test_negated_relocation_does_not_reject():
    result = analyze(
        "Remote position. No relocation required.",
        constraints=("no relocation",),
    )
    assert result["rejected"] is False


def test_explicit_mandatory_relocation_and_constraint_rejects():
    result = analyze(
        "Candidates must relocate to Dublin.",
        constraints=("no relocation",),
    )
    assert result["rejected"] is True


def test_closed_job_is_objective_and_rejects():
    result = analyze(
        "Applications are closed.",
    )
    assert result["rejected"] is True
