from contextlib import nullcontext
import pytest

from tests.test_workpilot_v1_onboarding_persistence import repo
from tests.test_v1_search_hiring_case_integration import search_service, RelationshipClient, offline
from tests.test_source_v2_foundation import job
from services.application_lifecycle_service import ApplicationLifecycleService
from services.application_lifecycle_repository import ApplicationLifecycleRepository
from services.application_outcome_repository import ApplicationOutcomeRepository
from services.application_outcome_service import ApplicationOutcomeService
from services.interview_round_repository import InterviewRoundRepository
from services.interview_preparation_service import InterviewPreparationService
from services.v1_apply_flow import V1ApplyFlow
from services.system_state_presenter import application_age_state
from models.application_tracking import InterviewRoundFeedback


@pytest.fixture
def relationship(repo):
    assert search_service(repo, RelationshipClient()).analyze_pending("a", limit=1)["failed"] == 0
    return "a", job().id


def apply(relationship):
    candidate, jid = relationship
    lifecycle = ApplicationLifecycleService()
    assert lifecycle.mark_ready_to_apply(candidate, jid).succeeded
    flow = V1ApplyFlow(preparation_service=None, lifecycle_service=lifecycle)
    assert flow.confirm_applied(candidate_id=candidate, job_id=jid, confirmed=False) is None
    assert flow.open_external("https://example.com/apply") == "https://example.com/apply"
    assert lifecycle.repository.get(candidate, jid)["status"] == "in_review"
    assert flow.confirm_applied(candidate_id=candidate, job_id=jid, confirmed=True).status == "applied"
    assert flow.confirm_applied(candidate_id=candidate, job_id=jid, confirmed=True).status == "already_applied"


def test_official_ready_applied_rounds_and_feedback_reach_later_brief(relationship):
    c, j = relationship
    rounds = InterviewRoundRepository()
    with pytest.raises(ValueError, match="active"):
        rounds.create(candidate_id=c, job_id=j, scheduled_at="")
    apply(relationship)
    first = rounds.create(candidate_id=c, job_id=j, scheduled_at="2026-10-01T10:00:00+01:00",
                          interview_id="round-one", interviewer_roles=("Recruiter",))
    rounds.save_feedback(InterviewRoundFeedback(first.interview_id, c, j,
        "Discussed incident handling.", "Prepare a grounded example."))
    second = rounds.create(candidate_id=c, job_id=j, scheduled_at="", interview_id="round-two")
    assert rounds.create(candidate_id=c, job_id=j, scheduled_at="", interview_id="round-two") == second
    service = InterviewPreparationService()
    brief = service.build_brief(c, j, second.interview_id)
    assert brief.round_sequence == 2
    assert brief.previous_round_refs == (first.interview_id,)
    assert brief.previous_round_feedback == ("Discussed incident handling.",)
    assert brief.next_stage_context == ("Prepare a grounded example.",)
    assert brief.company_context == () and brief.interviewer_contexts == ()
    assert brief.strongest_evidence and brief.strongest_evidence[0].evidence_refs
    assert service.build_brief(c, j, first.interview_id).previous_round_feedback == ()
    assert ApplicationOutcomeRepository().list_applications(c)[0]["application_group"] == "interview"
    assert rounds.list("other", j) == rounds.list(c, "other") == []
    for scope in (("other", j), (c, "other")):
        with pytest.raises((ValueError, PermissionError)):
            service.build_brief(*scope, second.interview_id)
    with pytest.raises(ValueError):
        rounds.save_feedback(InterviewRoundFeedback(first.interview_id, "other", j, "Injected"))
    third = rounds.create(candidate_id=c, job_id=j, scheduled_at="")
    assert third.sequence == 3


def test_no_response_and_aging_are_not_rejection(relationship):
    apply(relationship)
    c, j = relationship
    repository = ApplicationOutcomeRepository()
    before = repository.list_applications(c)
    state = application_age_state(applied_at="2020-01-01T00:00:00+00:00", now="2026-10-01T00:00:00+00:00")
    assert state.band == "old"
    assert repository.list_applications(c) == before
    assert before[0]["application_group"] == "applied"
    assert ApplicationOutcomeService().mark_no_response(c, j).succeeded
    current = repository.list_applications(c)
    assert current[0]["application_group"] == "no_response"
    assert current[0]["application_stage"] != "rejected"
    with pytest.raises(ValueError, match="active"):
        InterviewRoundRepository().create(candidate_id=c, job_id=j, scheduled_at="")


def test_repository_cannot_bypass_ready_boundary_or_racing_rejection(relationship):
    c, j = relationship
    repository = ApplicationLifecycleRepository()
    assert repository.mark_applied(c, j, "now") is None
    service = ApplicationLifecycleService()
    service.mark_ready_to_apply(c, j)
    service.mark_user_rejected(c, j)
    assert repository.mark_applied(c, j, "now") is None
    assert repository.get(c, j)["status"] == "user_rejected"


def test_ready_is_listed_and_preserves_candidate_scope(relationship):
    c, j = relationship
    ApplicationLifecycleService().mark_ready_to_apply(c, j)
    repository = ApplicationOutcomeRepository()
    assert repository.list_applications(c)[0]["application_group"] == "ready_to_apply"
    assert repository.list_applications("other") == []


def test_company_brief_uses_only_matching_public_registry_profile(relationship):
    from services.company_repository import CompanyRepository
    from services.company_profile_repository import CompanyProfileRepository
    from tests.test_workpilot_v1_company_profile import build
    from models.company_profile import CompanyProfileDraft, CompanyClaim
    apply(relationship)
    c, j = relationship
    company = CompanyRepository().get_or_create_company(job().company)
    profile = build(company.id, draft=CompanyProfileDraft(what_they_do="Provides software.",
        claims=(CompanyClaim("what_they_do", "Provides software.", "web:company"),)))
    CompanyProfileRepository().save(profile)
    round_ = InterviewRoundRepository().create(candidate_id=c, job_id=j, scheduled_at="")
    brief = InterviewPreparationService().build_brief(c, j, round_.interview_id)
    assert brief.company_id == company.id
    assert brief.company_context == ("Provides software.",)
    assert brief.company_claims == profile.claims
    assert brief.company_source_signature == profile.source_signature


def test_offer_closed_and_history_are_visible_without_mutating_relationship(relationship):
    apply(relationship)
    c, j = relationship
    InterviewRoundRepository().create(candidate_id=c, job_id=j, scheduled_at="")
    service = ApplicationOutcomeService()
    assert service.mark_offer(c, j).succeeded
    assert service.repository.list_applications(c)[0]["application_group"] == "offer"
    assert service.mark_accepted(c, j).succeeded
    item = service.repository.list_applications(c)[0]
    assert item["application_group"] == "closed" and item["application_stage"] == "accepted"
    assert InterviewRoundRepository().list(c, j)


class Rerun(Exception):
    pass


class UI:
    def __init__(self, pressed="", values=None):
        self.pressed = pressed
        self.values = values or {}
        self.session_state = {}
        self.output = []
    def form(self, *args):
        return nullcontext()
    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [nullcontext() for _ in range(count)]
    def checkbox(self, *args):
        return False
    def date_input(self, label, value):
        return value
    def time_input(self, label):
        from datetime import time
        return time(10)
    def text_input(self, label, value="", **kwargs):
        return self.values.get(label, value)
    text_area = text_input
    def button(self, label, **kwargs):
        return label == self.pressed
    form_submit_button = button
    def write(self, value):
        self.output.append(str(value))
    caption = write
    markdown = write
    subheader = write
    error = write
    warning = write
    def rerun(self):
        raise Rerun()


def test_runtime_round_ui_saves_feedback_and_renders_later_brief(relationship):
    from services.interview_preparation_ui import render_interview_rounds
    apply(relationship)
    c, j = relationship
    ui = UI("Add interview round", {"Interviewer roles (optional)": "Recruiter", "Notes": "Recorded source notes"})
    with pytest.raises(Rerun):
        render_interview_rounds(ui, candidate_id=c, job_id=j)
    first = InterviewRoundRepository().list(c, j)[0]
    assert first.interviewer_roles == ("Recruiter",)
    ui.pressed = "Save round feedback"
    ui.values = {"Feedback": "Discussed real examples", "Next steps": "Second interview"}
    with pytest.raises(Rerun):
        render_interview_rounds(ui, candidate_id=c, job_id=j)
    assert InterviewRoundRepository().feedback_for(first.interview_id, c, j).feedback_text == "Discussed real examples"
    InterviewRoundRepository().create(candidate_id=c, job_id=j, scheduled_at="")
    ui.pressed = "View interview brief"
    render_interview_rounds(ui, candidate_id=c, job_id=j)
    assert "#### Interview 1" in ui.output and "#### Interview 2" in ui.output
    assert "Discussed real examples" in ui.output and "Second interview" in ui.output
    assert "Public company context is not available." in ui.output
    assert not any("could not" in text for text in ui.output)


def test_current_applications_screen_uses_outcomes_and_safe_confirmed_apply():
    import ast
    from pathlib import Path
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "applications_main")
    render = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "render_job")
    assert "list_applications" in ast.unparse(main)
    main_source = ast.unparse(main)
    assert all(label in main_source for label in ("All", "Applied", "Interview", "Offer", "Closed"))
    assert "st.tabs" not in main_source
    assert "_application_filter_group" in main_source
    assert "external_application_url" in ast.unparse(render)
    assert "handle_mark_applied_action" in ast.unparse(render)
    assert "application_age_state" in ast.unparse(render)


def test_feedback_retry_preserves_timestamp_and_confirmed_apply_wins_over_stale_rejection(relationship):
    apply(relationship)
    c, j = relationship
    repository = ApplicationLifecycleRepository()
    assert repository.mark_user_rejected(c, j, "stale") is None
    assert repository.get(c, j)["status"] == "applied"
    rounds = InterviewRoundRepository()
    item = rounds.create(candidate_id=c, job_id=j, scheduled_at="")
    feedback = InterviewRoundFeedback(item.interview_id, c, j, "Recorded feedback")
    saved = rounds.save_feedback(feedback)
    assert rounds.save_feedback(feedback) == saved


def test_applications_render_open_link_is_passive_and_confirmation_is_explicit(relationship):
    import ast
    from pathlib import Path
    from datetime import datetime, timezone
    from services.external_application import external_application_url
    from services.application_lifecycle_ui import handle_mark_applied_action
    c, j = relationship
    lifecycle = ApplicationLifecycleService()
    lifecycle.mark_ready_to_apply(c, j)
    item = ApplicationOutcomeRepository().list_applications(c)[0]
    tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    render = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "render_job")
    ui = UI()
    ui.expander = lambda *a, **kw: nullcontext()
    ui.divider = lambda: None
    ui.link_button = lambda label, url: ui.output.append(url)
    ui.toast = ui.write
    namespace = dict(st=ui, datetime=datetime, timezone=timezone,
        application_age_state=application_age_state, external_application_url=external_application_url,
        handle_mark_applied_action=handle_mark_applied_action, ApplicationLifecycleService=ApplicationLifecycleService,
        render_job_analysis=lambda *a, **kw: None, render_interview_preparation=lambda **kw: None,
        render_application_outcome=lambda **kw: None)
    exec(compile(ast.Module(body=[render], type_ignores=[]), "app.py", "exec"), namespace)
    namespace["render_job"](c, item)
    assert lifecycle.repository.get(c, j)["status"] == "in_review"
    ui.pressed = "Yes, I applied"
    with pytest.raises(Rerun):
        namespace["render_job"](c, item)
    assert lifecycle.repository.get(c, j)["status"] == "applied"
