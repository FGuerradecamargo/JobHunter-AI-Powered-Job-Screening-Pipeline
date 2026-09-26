from dataclasses import asdict, replace
from types import SimpleNamespace
import pytest

from tests.test_tailored_cv_truth_guard import _context, _draft
from models.prepare_application import PrepareApplicationResult
from models.profile_interpretation import CandidateProfileSnapshot, ProfileCheckpoint, AIJobProfileSnapshot
from services.tailored_cv_edit_service import validate_edited_cv
from services.cv_keyword_coverage import check_ats_keyword_coverage
from services.v1_apply_flow import V1ApplyFlow, validate_apply_sources
from services.application_lifecycle_service import ApplicationLifecycleService


def grounded():
    context = _context()
    context.available_evidence[0].metadata.update(company="Example Ltd", stated_role="Operations Specialist")
    draft = _draft()
    draft = replace(draft, headline=replace(draft.headline, text="Process improvement"),
                    professional_summary=[replace(draft.professional_summary[0], text="Process improvement")],
                    additional_relevant_information=[draft.additional_relevant_information[0],
                        replace(draft.additional_relevant_information[1], text="Kubernetes fundamentals")])
    return context, draft


def profiles(context):
    c = CandidateProfileSnapshot(candidate_id=context.candidate_id, profile_version=1, memory_signature="m",
        created_at="now", source_refs=tuple(e.evidence_ref for e in context.available_evidence), capabilities=(),
        checkpoint=ProfileCheckpoint(current_position=""))
    j = AIJobProfileSnapshot(job_id=context.job_id, profile_version=1, job_signature="j", created_at="now", needs=())
    h = SimpleNamespace(candidate_id=c.candidate_id, job_id=j.job_id, candidate_profile_version=1,
        job_profile_version=1, candidate_signature="m", job_signature="j", hard_eligibility_blockers=[])
    return c, j, h


class LifecycleRepo:
    def __init__(self):
        self.row = dict(candidate_id="candidate-a", job_id="job-1", status="in_review", opportunity_state="selected", applied_at=None)
    def get(self, c, j):
        return dict(self.row) if (c, j) == ("candidate-a", "job-1") else None
    def mark_ready_to_apply(self, c, j, now):
        self.row["opportunity_state"] = "ready_to_apply"
        return self.get(c, j)
    def mark_applied(self, c, j, now):
        self.row.update(status="applied", opportunity_state="applied", applied_at=now)
        return self.get(c, j)


def flow(draft, context):
    result = PrepareApplicationResult(status="prepared", candidate_id=context.candidate_id, job_id=context.job_id,
        application_context_signature=context.source_signature, cv=draft, generation_status="validated")
    return V1ApplyFlow(preparation_service=SimpleNamespace(prepare=lambda c, j: result),
                       lifecycle_service=ApplicationLifecycleService(repository=LifecycleRepo()))


def test_generation_revalidated_progress_and_profile_immutable():
    context, draft = grounded()
    c, j, h = profiles(context)
    before = asdict(c)
    events = []
    result = flow(draft, context).prepare(candidate_profile=c, job_profile=j, hiring_case=h, context=context, progress=events.append)
    assert result.status == "prepared"
    assert list(dict.fromkeys(e.label for e in events)) == ["Matching your strongest evidence", "Adapting language to the role", "Checking ATS keywords", "Keeping everything defensible"]
    assert asdict(c) == before


def test_unsupported_generated_and_manual_text_flagged_not_removed():
    context, draft = grounded()
    bad = replace(draft, headline=replace(draft.headline, text="Led 200 engineers using Rust"))
    edited = validate_edited_cv(draft=bad, context=context)
    assert not edited.accepted and edited.cv == bad
    assert "unsupported_statement" in {i.code for i in edited.issues}
    c, j, h = profiles(context)
    assert flow(bad, context).prepare(candidate_profile=c, job_profile=j, hiring_case=h, context=context).status == "generation_failed"


def test_valid_edit_and_export_revalidate_mutation(monkeypatch):
    context, draft = grounded()
    service = flow(draft, context)
    valid = replace(draft, headline=replace(draft.headline, text="Process improvement."))
    assert service.edit(draft=valid, context=context).accepted
    export = service.export(draft=valid, context=context, candidate_name="Example", company="Target", role="Role")
    assert export.data.startswith(b"PK")
    valid.key_skills.append(replace(valid.key_skills[0], text="Invented licence"))
    with pytest.raises(ValueError):
        service.export(draft=valid, context=context, candidate_name="Example", company="Target", role="Role")


def test_ats_missing_evidence_and_missing_terminology_are_distinct():
    context, draft = grounded()
    context = replace(context, core_requirements=["SQL", "Legacy CRM", "Rust"])
    before = asdict(draft)
    coverage = check_ats_keyword_coverage(draft, context)
    assert coverage == {"matched": ["SQL"], "missing_with_evidence": ["Legacy CRM"], "missing_without_evidence": ["Rust"]}
    assert asdict(draft) == before


def test_ready_open_confirm_and_repeat_are_separate():
    context, draft = grounded()
    service = flow(draft, context)
    assert service.ready(draft=draft, context=context).status == "ready_to_apply"
    for _ in range(2):
        assert service.open_external("https://company.example/jobs/1") == "https://company.example/jobs/1"
    assert service.lifecycle.repository.row["status"] == "in_review"
    assert service.confirm_applied(candidate_id=context.candidate_id, job_id=context.job_id, confirmed=False) is None
    assert service.confirm_applied(candidate_id=context.candidate_id, job_id=context.job_id, confirmed=True).status == "applied"
    assert service.confirm_applied(candidate_id=context.candidate_id, job_id=context.job_id, confirmed=True).status == "already_applied"
    assert service.ready(draft=draft, context=context).status == "already_applied"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///tmp/cv", "data:text/html,x", "https://user:secret@example.com", "https://example.com\n/x"])
def test_unsafe_url_denied(url):
    context, draft = grounded()
    with pytest.raises(ValueError):
        flow(draft, context).open_external(url)


def test_stale_hiring_case_fails_before_generation():
    context, _ = grounded()
    c, j, h = profiles(context)
    h.job_profile_version = 2
    with pytest.raises(ValueError):
        validate_apply_sources(candidate_profile=c, job_profile=j, hiring_case=h, context=context)
