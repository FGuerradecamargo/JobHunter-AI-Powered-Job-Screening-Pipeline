from __future__ import annotations

from models.profile_interpretation import (
    AI_JOB_PROFILE_SCHEMA_VERSION,
    CANDIDATE_PROFILE_SCHEMA_VERSION,
    AIJobProfileSnapshot,
    CandidateProfileSnapshot,
    JobHardFacts,
    SourceEvidence,
)
from services.database import utc_now
from services.profile_interpreter import ProfileInterpreter
from services.profile_snapshot_repository import ProfileSnapshotRepository


class ProfileInterpretationService:
    def __init__(self, repository: ProfileSnapshotRepository, interpreter: ProfileInterpreter) -> None:
        self.repository = repository
        self.interpreter = interpreter

    def candidate_profile(
        self,
        *,
        candidate_id: str,
        memory_signature: str,
        memory_payload: dict,
        source_evidence: tuple[SourceEvidence, ...],
    ) -> CandidateProfileSnapshot:
        existing = self.repository.candidate_for_signature(
            candidate_id, memory_signature, CANDIDATE_PROFILE_SCHEMA_VERSION,
        )
        if existing is not None:
            return existing
        previous = self.repository.current_candidate(candidate_id)
        # Only source memory and source evidence enter interpretation. The previous
        # checkpoint is separate and may describe change, never satisfy evidence.
        draft = self.interpreter.build_candidate_profile(
            candidate_id=candidate_id,
            memory_payload=memory_payload,
            source_evidence=source_evidence,
            previous_checkpoint=(previous.checkpoint if previous else None),
        )
        available_refs = tuple(item.ref for item in source_evidence)
        profile = CandidateProfileSnapshot(
            candidate_id=candidate_id,
            profile_version=(previous.profile_version + 1 if previous else 1),
            supersedes_version=(previous.profile_version if previous else None),
            memory_signature=memory_signature,
            created_at=utc_now(),
            source_refs=available_refs,
            capabilities=draft.capabilities,
            checkpoint=draft.checkpoint,
            contexts=draft.contexts,
            evidence_summaries=draft.evidence_summaries,
            confirmed_gaps=draft.confirmed_gaps,
            evidence_gaps=draft.evidence_gaps,
            objectives=draft.objectives,
            preferences=draft.preferences,
            seniority=draft.seniority,
            responsibility_scope=draft.responsibility_scope,
        )
        self.repository.save_candidate(profile)
        return profile

    def job_profile(self, *, hard_facts: JobHardFacts) -> AIJobProfileSnapshot:
        existing = self.repository.job_for_signature(
            hard_facts.job_id, hard_facts.job_signature, AI_JOB_PROFILE_SCHEMA_VERSION,
        )
        if existing is not None:
            return existing
        previous = self.repository.current_job(hard_facts.job_id)
        draft = self.interpreter.build_job_profile(
            hard_facts=hard_facts, previous_profile=previous,
        )
        available = set(hard_facts.fact_refs)
        for need in draft.needs:
            if not set(need.hard_fact_refs).issubset(available):
                raise ValueError("Job interpretation cited an unknown hard-fact ref.")
            if need.hard_blocker:
                referenced = [item for item in hard_facts.facts if item.fact_id in need.hard_fact_refs]
                if not any(item.hard_blocker for item in referenced):
                    raise ValueError("AI interpretation cannot create a hard blocker.")
        profile = AIJobProfileSnapshot(
            job_id=hard_facts.job_id,
            profile_version=(previous.profile_version + 1 if previous else 1),
            supersedes_version=(previous.profile_version if previous else None),
            job_signature=hard_facts.job_signature,
            created_at=utc_now(),
            needs=draft.needs,
            problem_to_solve=draft.problem_to_solve,
            responsibilities=draft.responsibilities,
            context=draft.context,
            uncertainties=draft.uncertainties,
            tools_as_means=draft.tools_as_means,
        )
        self.repository.save_job(profile)
        return profile
