from __future__ import annotations

from typing import Protocol

from models.profile_interpretation import (
    AIJobProfileSnapshot,
    CandidateProfileDraft,
    CandidateProfileSnapshot,
    HiringCaseInterpretation,
    JobHardFacts,
    JobProfileDraft,
    ProfileCheckpoint,
    SourceEvidence,
)


class ProfileInterpreter(Protocol):
    """Provider-neutral structured interpretation. Implementations are untrusted."""

    def build_candidate_profile(
        self,
        *,
        candidate_id: str,
        memory_payload: dict,
        source_evidence: tuple[SourceEvidence, ...],
        previous_checkpoint: ProfileCheckpoint | None,
    ) -> CandidateProfileDraft: ...

    def build_job_profile(
        self,
        *,
        hard_facts: JobHardFacts,
        previous_profile: AIJobProfileSnapshot | None,
    ) -> JobProfileDraft: ...

    def analyze_hiring_case(
        self,
        *,
        candidate_profile: CandidateProfileSnapshot,
        job_profile: AIJobProfileSnapshot,
    ) -> HiringCaseInterpretation: ...
