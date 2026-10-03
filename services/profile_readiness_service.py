"""Read-only profile readiness, independent of product and commercial access."""
from dataclasses import dataclass

from streamlit.runtime.scriptrunner import (
    get_script_run_ctx,
)

from models.profile_interpretation import CANDIDATE_PROFILE_SCHEMA_VERSION, CandidateProfileSnapshot
from services.candidate_profile_source import load_confirmed_candidate_profile_input
from services.runtime_timing import timed


@dataclass(frozen=True)
class ProfileReadiness:
    status: str
    snapshot: CandidateProfileSnapshot | None = None

    @property
    def ready(self):
        return self.status == "ready"

    @property
    def message(self):
        return {
            "ready": "Your profile is ready.",
            "stale": "Your evidence has changed. Regenerate your profile before searching.",
            "missing": "Generate your profile from your confirmed experience before searching.",
            "no_evidence": "Confirm your experience in Profile before searching.",
            "unavailable": "Your profile could not be verified. Open Profile and try again.",
        }[self.status]


class ProfileReadinessService:
    def __init__(self, snapshots=None, onboarding=None, updates=None):
        from services.profile_snapshot_repository import ProfileSnapshotRepository
        from services.candidate_onboarding_repository import CandidateOnboardingRepository
        from services.career_update_repository import CareerUpdateRepository
        self.snapshots = snapshots if snapshots is not None else ProfileSnapshotRepository()
        self.onboarding = onboarding if onboarding is not None else CandidateOnboardingRepository()
        self.updates = updates if updates is not None else CareerUpdateRepository()

    @timed("profile.readiness")
    def check(self, candidate_id):
        if not candidate_id:
            return ProfileReadiness("no_evidence")
        source, evidence = load_confirmed_candidate_profile_input(candidate_id, self.onboarding, self.updates)
        if not any(e.source_type in {"professional_experience", "career_update"} for e in evidence):
            return ProfileReadiness("no_evidence")
        profile = self.snapshots.current_candidate(candidate_id)

        if isinstance(
            profile,
            CandidateProfileSnapshot,
        ) and (
            profile.candidate_id == candidate_id
            and bool(profile.raw_source_signature)
            and profile.raw_source_signature
            == source.source_signature
            and profile.schema_version
            == CANDIDATE_PROFILE_SCHEMA_VERSION
            and set(profile.source_refs).issubset(
                {
                    item.ref
                    for item in evidence
                }
            )
        ):
            return ProfileReadiness(
                "ready",
                profile,
            )

        return ProfileReadiness(
            "stale"
            if profile is not None
            else "missing"
        )

    def backfill_missing(self, candidate_id, interpreter):
        """Explicit migration only; never replace a Candidate or an existing snapshot."""
        previous = self.snapshots.current_candidate(candidate_id)
        if previous is not None:
            return previous
        from services.profile_interpretation_service import ProfileInterpretationService
        import sqlite3
        import psycopg
        try:
            return ProfileInterpretationService(self.snapshots, interpreter).candidate_profile_from_onboarding(
                candidate_id=candidate_id, onboarding_repository=self.onboarding,
                career_update_repository=self.updates,
            )
        except (sqlite3.IntegrityError, psycopg.IntegrityError):
            # Another tab may have persisted version 1 while interpretation ran.
            winner = self.snapshots.current_candidate(candidate_id)
            if winner is None:
                raise
            return winner


def _runtime_readiness_cache():
    """
    Return a cache that exists only for the current Streamlit
    script run.

    Streamlit replaces context.cursors on the next rerun, so
    profile mutations followed by st.rerun always receive a
    fresh readiness calculation.
    """
    context = get_script_run_ctx()

    if context is None:
        return None

    cursors = getattr(
        context,
        "cursors",
        None,
    )

    runtime = getattr(
        context,
        "_workpilot_profile_readiness_runtime",
        None,
    )

    if (
        runtime is None
        or runtime[0] is not cursors
    ):
        runtime = (
            cursors,
            {},
        )

        context._workpilot_profile_readiness_runtime = (
            runtime
        )

    return runtime[1]


def profile_readiness(candidate_id):
    normalized_candidate_id = str(
        candidate_id or ""
    ).strip()

    cache = _runtime_readiness_cache()

    if (
        cache is not None
        and normalized_candidate_id in cache
    ):
        return cache[
            normalized_candidate_id
        ]

    try:
        result = (
            ProfileReadinessService()
            .check(candidate_id)
        )

    except Exception:
        # Fail closed without leaking evidence or
        # database exception text.
        result = ProfileReadiness(
            "unavailable"
        )

    if cache is not None:
        cache[
            normalized_candidate_id
        ] = result

    return result
