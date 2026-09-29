import logging
from html import escape
from services.historical_cv_presenter import normalize_historical_cv
from services.opportunity_search_run import OpportunitySearchRun
from services.ai.prompt_builder import BATCH_MAX_SIZE
from models.system_state import SearchRunState
from services.system_state_presenter import (
    stopped_search_message, analysis_unavailable_notice, search_notice,
)

logger = logging.getLogger(__name__)

import streamlit as st
from services.profile_readiness_service import profile_readiness
from services.runtime_timing import timed, timed_page

from components.job_analysis_view import render_job_analysis
from components.workpilot_ui import apply_theme, page_header


from services.job_search_repository import JobSearchRepository
from services.session_auth import (
    render_logout_button,
    require_authenticated_user,
)
from services.user_context_runtime import get_active_user_context
from services.prepared_application_ui import (
    build_prepared_cv_view,
    handle_prepare_application_action,
    is_prepare_application_eligible,
    prepared_application_error_message,
)
from services.prepared_cv_exporter import export_cached_prepared_cv_docx
from services.application_lifecycle_service import ApplicationLifecycleService
from services.application_lifecycle_ui import (
    handle_mark_applied_action,
    handle_user_rejected_action,
)
from services.candidate_repository import CandidateRepository
from services.candidate_product_state_repository import (
    CandidateProductStateRepository,
)
from services.product_mode_policy import product_mode_policy
from services.career_objective_repository import CareerObjectiveRepository
from services.career_update_repository import CareerUpdateRepository
from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
    ANALYSIS_VERSION,
    build_candidate_signature,
)
from services.cv_renderer import (
    render_tailored_cv_docx,
    render_tailored_cv_pdf,
)
from services.ai_usage_budget import AIUsageBudget
from services.prepare_application_factory import (
    build_production_prepare_application_service,
)

from services.database import (
    activate_candidate_opportunities,
    ensure_candidate_job_analysis,
    list_candidate_jobs,
    list_inactive_approved_candidate_jobs,
    update_candidate_job_notes,
)


st.set_page_config(
    page_title="Jobs",
    page_icon=":material/work:",
    layout="wide",
)

authenticated_user = (
    require_authenticated_user()
)

user_context = (
    get_active_user_context(
        authenticated_user=authenticated_user
    )
)

active_user = user_context.active_user

render_logout_button(authenticated_user=authenticated_user)

repository = JobSearchRepository()
candidate_repository = CandidateRepository()
application_lifecycle_service = ApplicationLifecycleService()

analysis_service = None
analysis_configuration_error = ""

try:
    production_preparation_service = (
        build_production_prepare_application_service()
    )
    preparation_configuration_error = ""
except Exception:
    production_preparation_service = None
    preparation_configuration_error = (
        "Tailored CV generation is currently unavailable."
    )



if not active_user.candidate_id:
    st.error(
        "Your account does not have a professional profile."
    )
    st.stop()


candidate_id = active_user.candidate_id

readiness = profile_readiness(candidate_id)
if not readiness.ready:
    st.session_state.pop("scan_requested", None)
    st.session_state.pop("opportunity_search_run", None)
    st.session_state["scan_in_progress"] = False
    st.info(readiness.message)
    st.page_link("pages/3_Profile.py", label="Open Profile")
    st.stop()

candidate = candidate_repository.get(
    candidate_id
)

if candidate is None:
    st.error(
        "Could not load your professional profile."
    )
    st.stop()


product_state = CandidateProductStateRepository().get(
    candidate_id
)

product_policy = product_mode_policy(
    product_state
)

if not product_policy.can_search:
    if product_policy.mode.value == "career":
        st.info(
            "WorkPilot is in Career mode. "
            "Return to Search mode before looking for new opportunities."
        )
    else:
        st.info(
            "WorkPilot is currently read-only. "
            "Your existing career history remains available."
        )

    st.stop()


apply_theme()
page_header(
    "Jobs for you",
    "Opportunities interpreted against your profile, direction and what matters to you.",
    eyebrow="JOBS",
)

career_objective = (
    CareerObjectiveRepository()
    .get_active(candidate_id)
)

career_updates = (
    CareerUpdateRepository()
    .list_for_candidate(candidate_id)
)

candidate_signature = build_candidate_signature(
    candidate,
    career_objective,
    career_updates,
)


OPPORTUNITIES_CSS = """
<style>
    .wp-search-context {
        background: #FFFDF8;
        border: 1px solid #E7DED1;
        border-radius: 18px;
        padding: 1.15rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 24px rgba(31, 48, 53, 0.035);
    }
    .wp-search-context-head { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; margin-bottom:.85rem; }
    .wp-search-context h3 { margin:0 0 .15rem 0 !important; font-size:1rem !important; }
    .wp-search-context p { color:#6E7C7F; margin:0 !important; font-size:.82rem !important; }
    .wp-context-row, .wp-priority-row { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:.7rem; }
    .wp-context-chip { display:inline-flex; gap:.42rem; align-items:center; padding:.46rem .66rem; border-radius:999px; background:#F5EFE5; color:#30464E; border:1px solid #E6DDD1; font-size:.76rem; }
    .wp-context-chip strong { color:#173B4B; }
    .wp-priority-label { color:#173B4B; font-size:.72rem; font-weight:750; margin-top:.85rem; }
    .wp-priority-label span { color:#7A8587; font-weight:500; margin-left:.35rem; }
    .wp-priority-chip { display:inline-flex; padding:.34rem .62rem; border-radius:999px; background:#F5DFD0; color:#A74E26; font-size:.74rem; font-weight:700; }
    .wp-searching-card { display:grid; grid-template-columns:auto 1fr; gap:1rem; align-items:center; background:linear-gradient(105deg,#FFFDF8 0%,#F5EEE4 100%); border:1px solid #E7DED1; border-radius:18px; padding:1.2rem 1.3rem; margin:.75rem 0; }
    .wp-coffee-mark { width:52px; height:52px; border-radius:16px; display:grid; place-items:center; background:#F5DFD0; font-size:1.45rem; }
    .wp-searching-card h3 { margin:0 !important; }
    .wp-searching-card p { color:#6E7C7F; margin:.22rem 0 0 !important; }
    .wp-searching-line { height:5px; border-radius:999px; background:#E9E1D7; overflow:hidden; margin-top:.75rem; }
    .wp-searching-line::after { content:""; display:block; width:42%; height:100%; border-radius:inherit; background:#DD7338; }
    .wp-search-report { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.7rem; background:#FFFDF8; border:1px solid #E7DED1; border-radius:18px; padding:1rem; margin:1rem 0 1.6rem; }
    .wp-search-report > div { padding:.75rem; border-right:1px solid #EEE7DD; }
    .wp-search-report > div:last-child { border-right:0; }
    .wp-search-report strong { display:block; color:#173B4B; font-size:1.35rem; }
    .wp-search-report span { color:#6E7C7F; font-size:.74rem; }
    .wp-results-header { display:flex; align-items:end; justify-content:space-between; gap:1rem; margin:2rem 0 .9rem; }
    .wp-results-title { color:#173B4B; font-size:1.35rem; font-weight:800; }
    .wp-results-copy { color:#6E7C7F; font-size:.84rem; margin-top:.2rem; }
    .wp-category { padding:.75rem .2rem .6rem; margin-bottom:.35rem; }
    .wp-category-top { display:flex; align-items:center; justify-content:space-between; gap:.55rem; }
    .wp-category-title { color:#173B4B; font-size:1rem; font-weight:800; }
    .wp-category-count { background:#F1EADF; color:#173B4B; border-radius:999px; padding:.16rem .5rem; font-size:.7rem; font-weight:800; }
    .wp-category-copy { color:#6E7C7F; font-size:.76rem; margin-top:.25rem; min-height:2.4rem; }
    .wp-compact-job { background:#FFFDF8; border:1px solid #E7DED1; border-radius:16px; padding:.95rem; margin-bottom:.7rem; min-height:178px; box-shadow:0 8px 22px rgba(31,48,53,.035); }
    .wp-compact-job h4 { color:#173B4B; margin:.12rem 0 !important; font-size:.95rem !important; }
    .wp-compact-job-company { color:#566B70; font-size:.79rem; }
    .wp-compact-job-meta { color:#849093; font-size:.72rem; margin-top:.25rem; }
    .wp-compact-fit { display:grid; grid-template-columns:1fr 1fr; gap:.5rem; margin-top:.8rem; }
    .wp-compact-fit div { background:#F7F1E8; border-radius:10px; padding:.55rem; }
    .wp-compact-fit span { display:block; color:#7A8587; font-size:.62rem; }
    .wp-compact-fit strong { display:block; color:#173B4B; font-size:.78rem; margin-top:.1rem; }
    .wp-compact-reason { color:#617276; font-size:.75rem; line-height:1.45; margin:.65rem 0 0 !important; }
    .wp-empty-category { background:rgba(255,253,248,.55); border:1px dashed #D8CFC2; border-radius:14px; color:#748184; font-size:.8rem; padding:.9rem; }
    [data-testid="stMain"] [data-testid="stExpander"] { background:#FFFDF8 !important; border:1px solid #E7DED1 !important; border-radius:16px !important; overflow:hidden; margin-bottom:.75rem; }
    @media (max-width:900px) { .wp-search-report { grid-template-columns:repeat(2,1fr); } .wp-search-report > div { border-right:0; } }
</style>
"""
st.markdown(
    OPPORTUNITIES_CSS,
    unsafe_allow_html=True,
)



def render_opportunity_category_header(
    title: str,
    count: int,
    description: str,
) -> None:
    st.html(
        f"""
        <div class="wp-category">
            <div class="wp-category-top">
                <div class="wp-category-title">
                    {title}
                </div>
                <div class="wp-category-count">
                    {count}
                </div>
            </div>
            <div class="wp-category-copy">
                {description}
            </div>
        </div>
        """
    )


def render_empty_category(
    message: str,
) -> None:
    st.html(
        f"""
        <div class="wp-empty-category">
            {message}
        </div>
        """
    )


DEFAULT_OPPORTUNITY_TARGET = 10

def empty_scan_result() -> dict:
    return {
        "selected": 0,
        "analyzed": 0,
        "hard_rejected": 0,
        "ai_eligible": 0,
        "ai_analyses_created": 0,
        "ai_approved": 0,
        "ai_rejected": 0,
        "best_match": 0,
        "potential": 0,
        "good_opportunity": 0,

        # Candidate-visible opportunities activated
        # during this scan.
        "activated_best_match": 0,
        "activated_potential": 0,
        "activated_good_opportunity": 0,

        "opportunities_found": 0,
        "target_reached": False,
        "usage_limit_reached": False,
        "provider_quota_exhausted": False,
        "descriptions_reused": 0,
        "descriptions_fetched": 0,
        "descriptions_failed": 0,
        "failed": 0,
        "errors": [],
        "batch_market_signals": [],
        "batch_ai_job_ids": [],
    }


def merge_scan_result(
    total: dict,
    batch: dict,
) -> None:
    numeric_keys = (
        "selected",
        "analyzed",
        "hard_rejected",
        "ai_eligible",
        "ai_analyses_created",
        "ai_approved",
        "ai_rejected",
        "best_match",
        "potential",
        "good_opportunity",
        "opportunities_found",
        "descriptions_reused",
        "descriptions_fetched",
        "descriptions_failed",
        "failed",
    )

    for key in numeric_keys:
        total[key] = (
            total.get(key, 0)
            + batch.get(key, 0)
        )

    total["errors"].extend(
        batch.get(
            "errors",
            [],
        )
    )

    total["batch_market_signals"].extend(
        batch.get(
            "batch_market_signals",
            [],
        )
    )

    total["batch_ai_job_ids"].extend(
        batch.get(
            "batch_ai_job_ids",
            [],
        )
    )

    total["usage_limit_reached"] = (
        total.get(
            "usage_limit_reached",
            False,
        )
        or batch.get(
            "usage_limit_reached",
            False,
        )
    )

    total["provider_quota_exhausted"] = (
        total.get(
            "provider_quota_exhausted",
            False,
        )
        or batch.get(
            "provider_quota_exhausted",
            False,
        )
    )


def activate_ready_opportunities(
    candidate_id: str,
    limit: int,
) -> dict:
    """
    Activate up to `limit` worthwhile analyses that are
    already complete but not yet visible to the candidate.
    """
    empty_result = {
        "job_ids": [],
        "best_match": 0,
        "potential": 0,
        "good_opportunity": 0,
    }

    if limit <= 0:
        return empty_result

    ready_jobs = (
        list_inactive_approved_candidate_jobs(
            candidate_id=candidate_id,
            limit=limit,
        )
    )

    ready_job_ids = [
        str(job["id"])
        for job in ready_jobs
    ]

    activated_ids = (
        activate_candidate_opportunities(
            candidate_id=candidate_id,
            job_ids=ready_job_ids,
        )
    )

    if not activated_ids:
        return empty_result

    activated_set = set(
        activated_ids
    )

    result = {
        "job_ids": activated_ids,
        "best_match": 0,
        "potential": 0,
        "good_opportunity": 0,
    }

    for job in ready_jobs:
        if str(job["id"]) not in activated_set:
            continue

        recommendation = job.get(
            "recommendation"
        )

        if recommendation in {
            "best_match",
            "apply",
            "recommended_apply",
        }:
            result["best_match"] += 1

        elif recommendation == "potential":
            result["potential"] += 1

        elif recommendation in {
            "good_opportunity",
            "worth_second_look",
        }:
            result[
                "good_opportunity"
            ] += 1

    return result


def merge_activation_result(
    aggregate: dict,
    activation: dict,
) -> None:
    aggregate[
        "opportunities_found"
    ] += len(
        activation.get(
            "job_ids",
            [],
        )
    )

    aggregate[
        "activated_best_match"
    ] += activation.get(
        "best_match",
        0,
    )

    aggregate[
        "activated_potential"
    ] += activation.get(
        "potential",
        0,
    )

    aggregate[
        "activated_good_opportunity"
    ] += activation.get(
        "good_opportunity",
        0,
    )


search_scope = (
    authenticated_user.id,
    active_user.id,
    candidate_id,
    candidate_signature,
)

search_run = st.session_state.get(
    "opportunity_search_run"
)

_analysis_requested = bool(
    st.session_state.get(
        "scan_requested"
    )
) or (
    search_run is not None
    and search_run.status == "running"
    and search_run.scope == search_scope
)

if (
    _analysis_requested
    and analysis_service is None
):
    try:
        analysis_service = (
            CandidateJobAnalysisService()
        )

    except Exception:
        analysis_service = None
        analysis_configuration_error = (
            "Opportunity analysis is "
            "currently unavailable."
        )
if search_run is not None and search_run.scope != search_scope:
    # A changed actor, candidate or profile must not continue an older search.
    st.session_state.pop("opportunity_search_run", None)
    search_run = None
    for key in (
        "last_scan_result", "last_scan_total", "last_links_created",
        "last_scan_target", "last_pool_remaining",
    ):
        st.session_state.pop(key, None)

st.session_state["scan_in_progress"] = (
    search_run is not None and search_run.status == "running"
)
# Streamlit Community Cloud forces runner.fastReruns=True.
# Search safety comes from one persisted unit per rerun plus DB claims,
# not from requiring a particular Streamlit rerun mode.
search_execution_ready = True


def request_opportunity_scan() -> None:
    st.session_state["scan_requested"] = True


def stop_opportunity_scan(scope: tuple, scan_id: str) -> None:
    run = st.session_state.get("opportunity_search_run")
    if run is not None:
        run.stop(scope, scan_id)


pool_available = repository.count_jobs_to_analyze_for_candidate(
    candidate_id=candidate_id,
    analysis_version=ANALYSIS_VERSION,
    candidate_signature=candidate_signature,
)

direction_values = list(
    getattr(career_objective, "desired_role_families", None)
    or candidate.target_role_families
    or candidate.target_roles
    or ([candidate.current_role] if candidate.current_role else [])
)
priorities = list(getattr(candidate, "priorities", None) or [])
active_priorities = [
    priority.text
    for priority in priorities
    if priority.active and priority.direction == "positive"
]
deal_breakers = [
    priority.text
    for priority in priorities
    if priority.active and priority.direction != "positive"
]
preferences = getattr(candidate, "preferences", None)
work_modes = [
    label
    for label, allowed in (
        ("Remote", bool(getattr(preferences, "remote_allowed", False))),
        ("Hybrid", bool(getattr(preferences, "hybrid_allowed", False))),
        ("On-site", bool(getattr(preferences, "onsite_allowed", False))),
    )
    if allowed
]


def _context_chip(label: str, values: list[str]) -> str:
    value = " / ".join(str(item) for item in values if item) or "Not set"
    return (
        '<span class="wp-context-chip"><strong>' + escape(label) + '</strong> '
        + escape(value) + '</span>'
    )


st.html(
    '''<section class="wp-search-context">
      <div class="wp-search-context-head">
        <div>
          <h3>Searching based on your profile</h3>
          <p>Your direction, preferences and priorities shape what WorkPilot looks at first.</p>
        </div>
      </div>
      <div class="wp-context-row">'''
    + _context_chip("Direction", direction_values[:3])
    + _context_chip("Work mode", work_modes)
    + '''</div>
      <div class="wp-priority-label">Priorities <span>things WorkPilot should favor</span></div>
      <div class="wp-priority-row">'''
    + ''.join('<span class="wp-priority-chip">' + escape(item) + '</span>' for item in active_priorities[:5])
    + '''</div>
    </section>'''
)

with st.expander("Adjust search", expanded=False):
    st.caption("Priorities — things WorkPilot should favor")
    st.caption("Deal breakers — conditions that rule a job out")
    st.write("WorkPilot uses your current profile rather than a typed job title to drive normal search.")
    if active_priorities:
        st.caption("Active priorities: " + " · ".join(active_priorities))
    if deal_breakers:
        st.caption("Deal breakers: " + " · ".join(deal_breakers))
    st.page_link("pages/3_Profile.py", label="Update profile and direction →")

target_opportunities = DEFAULT_OPPORTUNITY_TARGET
with st.form("opportunity_search_controls"):
    st.form_submit_button(
        "Searching for opportunities..."
        if st.session_state["scan_in_progress"]
        else "Find opportunities for me",
        type="primary",
        use_container_width=True,
        disabled=(
            st.session_state["scan_in_progress"]
            or not search_execution_ready
        ),
        on_click=request_opportunity_scan,
    )
if analysis_configuration_error:
    st.caption(analysis_configuration_error)

if (st.session_state.pop("scan_requested", False)
        and not st.session_state["scan_in_progress"]
        and search_execution_ready and analysis_service is not None):
    search_run = OpportunitySearchRun(
        authenticated_user_id=authenticated_user.id,
        active_user_id=active_user.id,
        candidate_id=candidate_id,
        context_signature=candidate_signature,
        target=target_opportunities,
        aggregate=empty_scan_result(),
        budget=AIUsageBudget.unlimited(),
    )
    st.session_state["opportunity_search_run"] = search_run
    st.rerun()


@timed("opportunities.search_unit")
def advance_opportunity_search() -> bool:
    # No Streamlit output inside this unit: finish persistence before yielding.
    aggregate = search_run.aggregate
    if not search_run.initialized:
        merge_activation_result(
            aggregate,
            activate_ready_opportunities(candidate_id, search_run.target),
        )
        search_run.initialized = True
        return aggregate["opportunities_found"] < search_run.target

    if aggregate["opportunities_found"] >= search_run.target:
        return False

    buffer = search_run.prepared_job_ids
    flush = len(buffer) == BATCH_MAX_SIZE
    exhausted = False
    jobs = []
    if not flush:
        jobs = repository.list_jobs_to_analyze_for_candidate(
            candidate_id=candidate_id,
            analysis_version=ANALYSIS_VERSION,
            candidate_signature=candidate_signature,
            limit=1,
            target_families=candidate.target_role_families,
            bridge_families=candidate.bridge_role_families,
            competitive_families=candidate.competitive_role_families,
            exclude_job_ids=sorted(search_run.unavailable_job_ids | set(buffer)),
        )
        exhausted = not jobs
        flush = exhausted and bool(buffer)
        if exhausted and not buffer:
            return False

    if flush:
        requested_ids = list(buffer)
        batch_result = analysis_service.analyze_pending(
            candidate_id=candidate_id, limit=len(requested_ids),
            ai_budget=search_run.budget, job_ids=requested_ids,
            scan_id=search_run.scan_id, require_full_batch=not exhausted,
        )
        eligible = batch_result.get("ai_eligible_job_ids", [])
        # A partial claim/revalidation result is refilled before any paid call.
        buffer[:] = eligible if batch_result.get("recommendation_deferred") else []
        search_run.unavailable_job_ids.update(batch_result.get("unavailable_job_ids", []))
        # Preparation was already counted on earlier reruns.
        batch_result = dict(batch_result)
        for key in ("selected", "ai_eligible", "descriptions_reused",
                    "descriptions_fetched", "descriptions_failed"):
            batch_result[key] = 0
    else:
        job_id = str(jobs[0]["id"])
        if ensure_candidate_job_analysis(candidate_id=candidate_id, job_id=job_id):
            search_run.links_created += 1
        batch_result = analysis_service.analyze_pending(
            candidate_id=candidate_id, limit=1,
            ai_budget=search_run.budget, job_ids=[job_id],
            scan_id=search_run.scan_id, prepare_only=True,
        )
        for prepared_id in batch_result.get("ai_eligible_job_ids", []):
            if prepared_id not in buffer:
                buffer.append(prepared_id)
        if batch_result.get("selected") == 0 and not (
            batch_result.get("failed") or batch_result.get("usage_limit_reached")
            or batch_result.get("provider_quota_exhausted")
        ):
            search_run.unavailable_job_ids.add(job_id)
    merge_scan_result(aggregate, batch_result)
    merge_activation_result(
        aggregate,
        activate_ready_opportunities(
            candidate_id,
            max(0, search_run.target - aggregate["opportunities_found"]),
        ),
    )
    if batch_result.get("failed", 0):
        search_run.status = "failed"
    return (
        aggregate["opportunities_found"] < search_run.target
        and not batch_result.get("failed", 0)
        and not batch_result.get("usage_limit_reached", False)
        and not batch_result.get("provider_quota_exhausted", False)
    )


if search_run is not None:

    aggregate = search_run.aggregate
    aggregate["target_reached"] = aggregate["opportunities_found"] >= search_run.target
    st.session_state["last_scan_result"] = aggregate
    st.session_state["last_scan_total"] = aggregate["selected"]
    st.session_state["last_links_created"] = search_run.links_created
    st.session_state["last_scan_target"] = search_run.target
    st.session_state["last_pool_remaining"] = pool_available
    st.session_state["scan_in_progress"] = search_run.status == "running"
    if search_run.status == "stopped":
        st.info(stopped_search_message(opportunities_kept=aggregate['opportunities_found']))


scan_result = st.session_state.get(
    "last_scan_result"
)

if scan_result and not st.session_state.get("scan_in_progress", False):
    opportunities_found = scan_result.get("opportunities_found", 0)
    best_count = scan_result.get("activated_best_match", 0)
    worth_count = scan_result.get("activated_potential", 0)
    strong_count = scan_result.get("activated_good_opportunity", 0)
    failed = scan_result.get("failed", 0)
    provider_unavailable = bool(scan_result.get("provider_quota_exhausted"))

    # A search report is useful only when there is something real to summarize.
    # Do not present a row of zeroes after a provider/runtime failure.
    if opportunities_found:
        st.html(
            f'''<section class="wp-search-report">
              <div><strong>{opportunities_found}</strong><span>Worth reviewing</span></div>
              <div><strong>{best_count}</strong><span>Best Match</span></div>
              <div><strong>{worth_count}</strong><span>Worth a Try</span></div>
              <div><strong>{strong_count}</strong><span>You’re Strong, But</span></div>
            </section>'''
        )

    search_failed = failed or (search_run is not None and search_run.status == "failed")
    if provider_unavailable:
        st.warning(analysis_unavailable_notice().message)
    elif search_failed:
        st.warning(
            "Search couldn’t finish this time. Any opportunities already found are safe. "
            "You can try again when you’re ready."
        )
    if provider_unavailable or search_failed:
        st.button(
            "Try again",
            key="retry_opportunity_search",
            on_click=request_opportunity_scan,
        )


review_jobs = list_candidate_jobs(
    candidate_id=candidate_id,
    status="in_review",
)


best_matches = []
potential_jobs = []
good_opportunities = []

for job in review_jobs:
    analysis = job.get(
        "analysis",
        {},
    )

    bucket = (
        analysis.get("bucket")
        or analysis.get("recommendation")
    )

    if bucket == "best_match":
        best_matches.append(job)

    elif bucket == "potential":
        potential_jobs.append(job)

    elif bucket == "good_opportunity":
        good_opportunities.append(job)


def clean_display_bullet(value: str) -> str:
    text = str(value or "").strip()

    while text.startswith(("-", "*", "?")):
        text = text[1:].strip()

    return text


def build_cv_filename(
    candidate_name: str,
    company: str,
    title: str,
) -> str:
    def clean(value: str) -> str:
        value = value.strip()

        safe = "".join(
            character
            if character.isalnum()
            else "_"
            for character in value
        )

        while "__" in safe:
            safe = safe.replace(
                "__",
                "_",
            )

        return safe.strip("_")

    parts = [
        clean(candidate_name),
        clean(company),
        clean(title),
        "CV",
    ]

    parts = [
        part
        for part in parts
        if part
    ]

    return "_".join(parts) + ".docx"


def render_tailored_cv(
    analysis: dict,
    candidate_name: str,
    company: str,
    title: str,
) -> None:
    tailored_cv = normalize_historical_cv(analysis.get("tailored_cv"))

    if not tailored_cv:
        return

    with st.expander("Historical Tailored CV"):
        headline = tailored_cv.get(
            "headline",
            "",
        )

        if headline:
            st.text(headline)

        professional_summary = (
            tailored_cv.get(
                "professional_summary",
                "",
            )
        )

        if professional_summary:
            st.subheader(
                "Professional Summary"
            )
            st.text(
                professional_summary
            )

        key_skills = tailored_cv.get(
            "key_skills",
            [],
        )

        if key_skills:
            st.subheader(
                "Key Skills"
            )

            for skill in key_skills:
                st.text(
                    f"- {skill}"
                )

        experiences = tailored_cv.get(
            "experiences",
            [],
        )

        if experiences:
            st.subheader(
                "Relevant Experience"
            )

            for experience in experiences:
                role = experience.get(
                    "role",
                    "",
                )

                company_name = (
                    experience.get(
                        "company",
                        "",
                    )
                )

                heading_parts = [
                    value
                    for value in [
                        role,
                        company_name,
                    ]
                    if value
                ]

                if heading_parts:
                    st.text(" - ".join(heading_parts))

                for bullet in experience.get(
                    "tailored_bullets",
                    [],
                ):
                    clean_bullet = clean_display_bullet(
                        bullet
                    )

                    if clean_bullet:
                        st.text(
                            f"- {clean_bullet}"
                        )

        additional_information = (
            tailored_cv.get(
                "additional_relevant_information",
                [],
            )
        )

        if additional_information:
            st.subheader(
                "Additional Relevant Information"
            )

            for item in additional_information:
                clean_item = clean_display_bullet(
                    item
                )

                if clean_item:
                    st.text(
                        f"- {clean_item}"
                    )

        docx_data = render_tailored_cv_docx(
            candidate_name=candidate_name,
            tailored_cv=tailored_cv,
        )

        pdf_data = render_tailored_cv_pdf(
            candidate_name=candidate_name,
            tailored_cv=tailored_cv,
        )

        docx_filename = build_cv_filename(
            candidate_name=candidate_name,
            company=company,
            title=title,
        )

        pdf_filename = (
            docx_filename.removesuffix(".docx")
            + ".pdf"
        )

        download_columns = st.columns(2)

        with download_columns[0]:
            st.download_button(
                "Download CV (.docx)",
                data=docx_data,
                file_name=docx_filename,
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                use_container_width=True,
            )

        with download_columns[1]:
            st.download_button(
                "Download CV (.pdf)",
                data=pdf_data,
                file_name=pdf_filename,
                mime="application/pdf",
                use_container_width=True,
            )



def _compact_job_card(job: dict) -> None:
    analysis = job.get("analysis", {}) or {}
    raw_case = analysis.get("hiring_case")
    case = raw_case if (
        isinstance(raw_case, dict)
        and raw_case.get("authority") == "deterministic_hiring_case"
        and raw_case.get("schema_version") == "hiring-case-v2"
    ) else {}
    title = escape(str(job.get("title") or "Untitled role"))
    company = escape(str(job.get("company") or "Unknown company"))
    location = escape(str(job.get("location") or "Location unavailable"))

    if case:
        you_company = str(case.get("hiring_case_strength", "Unknown")).replace("_", " ").title()
        opportunity = case.get("opportunity", {}) or {}
        job_you = str(opportunity.get("value", "Unknown")).replace("_", " ").title()
        reason = str(case.get("decision_reason") or "Evidence-based analysis available.")
    else:
        you_company = str(job.get("current_fit") or "See analysis")
        job_you = str(job.get("growth_value") or "See analysis")
        reason = str(
            analysis.get("simple_summary")
            or analysis.get("final_reason")
            or "Open the analysis to review the evidence and trade-offs."
        )

    if len(reason) > 130:
        reason = reason[:127].rstrip() + "…"

    st.html(
        f'''<article class="wp-compact-job">
          <h4>{title}</h4>
          <div class="wp-compact-job-company">{company}</div>
          <div class="wp-compact-job-meta">{location}</div>
          <div class="wp-compact-fit">
            <div><span>You → Company</span><strong>{escape(you_company)}</strong></div>
            <div><span>Job → You</span><strong>{escape(job_you)}</strong></div>
          </div>
          <p class="wp-compact-reason">{escape(reason)}</p>
        </article>'''
    )


def render_job(
    job: dict,
    *,
    expanded: bool = False,
) -> None:
    analysis = job.get(
        "analysis",
        {},
    )

    title = job.get(
        "title",
    ) or "Untitled role"

    company = job.get(
        "company",
    ) or "Unknown company"

    with st.expander(
        f"{title} - {company}",
        expanded=expanded,
    ):
        render_job_analysis(
            job,
        )

        render_tailored_cv(
            analysis=analysis,
            candidate_name=candidate.name,
            company=company,
            title=title,
        )

        job_id = str(job["id"])
        eligible_for_preparation = is_prepare_application_eligible(analysis)
        if eligible_for_preparation:
            preparation_service = st.session_state.get(
                "_prepare_application_service",
                production_preparation_service,
            )
            st.caption(
                "Generates a tailored CV for this opportunity using AI."
            )
            if preparation_configuration_error:
                st.caption(preparation_configuration_error)
            prepare_requested = st.button(
                "Prepare Application",
                key=f"prepare_application_{candidate_id}_{job_id}",
                type="primary",
                use_container_width=True,
                disabled=preparation_service is None,
            )
            prepared_result = handle_prepare_application_action(
                st.session_state,
                candidate_id=candidate_id,
                job_id=job_id,
                analysis=analysis,
                action_requested=prepare_requested,
                preparation_service=preparation_service,
            )
            prepared_view = (
                build_prepared_cv_view(prepared_result)
                if prepared_result is not None
                else None
            )
            if prepared_view is not None:
                st.success(prepared_view.status_text)
                with st.expander("Prepared CV", expanded=True):
                    if prepared_view.headline:
                        st.markdown(f"### {prepared_view.headline}")
                    if prepared_view.professional_summary:
                        st.subheader("Professional Summary")
                        for item in prepared_view.professional_summary:
                            st.write(item)
                    if prepared_view.key_skills:
                        st.subheader("Key Skills")
                        for item in prepared_view.key_skills:
                            st.write(f"- {item}")
                    if prepared_view.experiences:
                        st.subheader("Professional Experience")
                        for experience in prepared_view.experiences:
                            heading = " - ".join(
                                item
                                for item in (experience.role, experience.company)
                                if item
                            )
                            if heading:
                                st.markdown(f"**{heading}**")
                            for bullet in experience.bullets:
                                st.write(f"- {bullet}")
                    if prepared_view.additional_information:
                        st.subheader("Additional Relevant Information")
                        for item in prepared_view.additional_information:
                            st.write(f"- {item}")
                try:
                    prepared_export = export_cached_prepared_cv_docx(
                        st.session_state,
                        candidate_id=candidate_id,
                        job_id=job_id,
                        candidate_name=candidate.name,
                        company=company,
                        role=title,
                    )
                except (ValueError, PermissionError):
                    st.warning("This CV needs review against your current evidence before download.")
                else:
                    st.download_button(
                        "Download prepared CV",
                        data=prepared_export.data,
                        file_name=prepared_export.filename,
                        mime=prepared_export.mime_type,
                        key=f"download_prepared_cv_{candidate_id}_{job_id}",
                        use_container_width=True,
                    )
                    if st.button("Ready to apply", key=f"ready_{candidate_id}_{job_id}"):
                        ready = application_lifecycle_service.mark_ready_to_apply(candidate_id, job_id)
                        if ready.succeeded:
                            st.rerun()
                        st.warning("This opportunity changed. Refresh before continuing.")
            elif prepared_result is not None:
                st.error(prepared_application_error_message(prepared_result))

        st.divider()

        st.markdown(
            "**Your notes**"
        )

        notes_value = st.text_area(
            "Personal notes",
            value=job.get(
                "notes",
                "",
            ),
            key=f"analysis_notes_{candidate_id}_{job_id}",
            label_visibility="collapsed",
            placeholder=(
                "Add anything useful for your decision: "
                "salary, concerns, questions, recruiter details..."
            ),
        )

        if st.button(
            "Save notes",
            key=f"save_analysis_notes_{candidate_id}_{job_id}",
            use_container_width=True,
        ):
            update_candidate_job_notes(
                candidate_id=candidate_id,
                job_id=job_id,
                notes=notes_value,
            )

            st.toast(
                "Notes saved."
            )

        st.markdown(
            "**Your decision**"
        )

        decision_columns = st.columns(2)

        with decision_columns[0]:
            reject_requested = st.button(
                "Do not apply",
                key=f"analysis_reject_{candidate_id}_{job_id}",
                use_container_width=True,
            )
            reject_result = handle_user_rejected_action(
                action_requested=reject_requested,
                candidate_id=candidate_id,
                job_id=job_id,
                lifecycle_service=application_lifecycle_service,
            )
            if reject_result is not None and reject_result.succeeded:
                st.rerun()

        with decision_columns[1]:
            apply_requested = st.button(
                "Mark as Applied",
                key=f"analysis_apply_{candidate_id}_{job_id}",
                type="primary",
                disabled=job.get("opportunity_state") != "ready_to_apply",
                use_container_width=True,
            )
            apply_result = handle_mark_applied_action(
                action_requested=apply_requested,
                candidate_id=candidate_id,
                job_id=job_id,
                lifecycle_service=application_lifecycle_service,
            )
            if apply_result is not None and apply_result.succeeded:
                st.toast("Opportunity marked as applied.")
                st.rerun()

        url = job.get(
            "url"
        )

        if url:
            st.link_button(
                "Open job",
                url,
                use_container_width=True,
            )


if (
    best_matches
    or potential_jobs
    or good_opportunities
):
    total_visible = len(best_matches) + len(potential_jobs) + len(good_opportunities)

    st.html(
        f'''<div class="wp-results-header">
          <div>
            <div class="wp-results-title">Your opportunities</div>
            <div class="wp-results-copy">{total_visible} opportunities are worth your attention right now.</div>
          </div>
        </div>'''
    )

    category_columns = st.columns(3, gap="medium")
    categories = (
        (category_columns[0], "Best Match", best_matches, "Strong alignment for you and for the employer."),
        (category_columns[1], "Worth a Try", potential_jobs, "Interesting opportunities with some stretch or evidence gaps."),
        (category_columns[2], "You’re Strong, But", good_opportunities, "You may compete well, but the role may offer less of what you want."),
    )

    for column, title, jobs, description in categories:
        with column:
            render_opportunity_category_header(title, len(jobs), description)
            if not jobs:
                render_empty_category("Nothing in this category right now.")
            for job in jobs:
                _compact_job_card(job)
                if st.button(
                    "View analysis →",
                    key=f"view_analysis_{candidate_id}_{job['id']}",
                    use_container_width=True,
                ):
                    st.session_state["selected_opportunity_id"] = str(job["id"])

    selected_id = st.session_state.get("selected_opportunity_id")
    selected_job = next(
        (
            job
            for job in [*best_matches, *potential_jobs, *good_opportunities]
            if str(job["id"]) == str(selected_id)
        ),
        None,
    )
    if selected_job is not None:
        st.divider()
        st.subheader("Job analysis")
        render_job(selected_job, expanded=True)

elif (scan_result and not st.session_state.get("scan_in_progress", False)
      and not scan_result.get("provider_quota_exhausted")
      and not scan_result.get("failed", 0)):
    render_empty_category(
        "Nothing worthwhile surfaced in this search. Your profile has not failed — "
        "the current opportunities simply did not clear the recommendation threshold."
    )


@st.fragment(run_every=0.5 if search_run is not None and search_run.status == "running" else None)
@timed_page("Jobs")
def render_search_progress():
    run = st.session_state.get("opportunity_search_run")
    if run is None or run.scope != search_scope:
        return
    if run.status != "running":
        if st.session_state.get("scan_in_progress"):
            st.rerun()
        return
    # Fragment reruns must revalidate authorization, not reuse an old identity.
    actor = require_authenticated_user()
    context = get_active_user_context(authenticated_user=actor)
    current = profile_readiness(candidate_id)
    if (actor.id != run.authenticated_user_id or context.active_user.id != run.active_user_id
            or context.active_user.candidate_id != candidate_id or not current.ready
            or current.snapshot.memory_signature != readiness.snapshot.memory_signature
            or not product_mode_policy(CandidateProductStateRepository().get(candidate_id)).can_search):
        run.stop(search_scope, run.scan_id)
        st.rerun()
    with st.container(key="persistent_search_progress"):
        st.subheader("Searching for opportunities...")
        st.caption("WorkPilot is still searching.")
        st.write(f"Reviewed: {run.aggregate.get('selected', 0)}")
        st.write(f"Passed initial screening: {run.aggregate.get('ai_eligible', 0)}")
        st.write(f"Preparing deeper analysis: {len(run.prepared_job_ids)}/{BATCH_MAX_SIZE}")
        st.button("Stop search", key="stop_opportunity_search",
                  on_click=stop_opportunity_scan, args=(search_scope, run.scan_id))
    run.advance(search_scope, advance_opportunity_search)
    if run.status != "running":
        st.rerun()


render_search_progress()
