from __future__ import annotations

from models.profile_interpretation import (
    AI_JOB_PROFILE_SCHEMA_VERSION,
    CANDIDATE_PROFILE_SCHEMA_VERSION,
    AIJobProfileSnapshot,
    CandidateProfileSnapshot,
    JobHardFacts,
    SourceEvidence,
    CoverageState,
)
from dataclasses import asdict
from services.candidate_profile_source import load_confirmed_candidate_profile_input
from services.database import utc_now
from services.profile_interpreter import ProfileInterpreter
from services.profile_snapshot_repository import ProfileSnapshotRepository


class ProfileInterpretationService:
    def __init__(self, repository: ProfileSnapshotRepository, interpreter: ProfileInterpreter) -> None:
        self.repository = repository
        self.interpreter = interpreter

    def candidate_profile_from_onboarding(self, *, candidate_id, onboarding_repository):
        snapshot, sources = load_confirmed_candidate_profile_input(candidate_id, onboarding_repository)
        if not sources:
            raise ValueError("Confirmed candidate source evidence is not available.")
        return self.candidate_profile(candidate_id=candidate_id,
            memory_signature=snapshot.source_signature, memory_payload=snapshot.payload,
            source_evidence=sources)

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
        if memory_payload.get("source_schema") == "confirmed-onboarding-v1" and any(
            state is CoverageState.CONFIRMED_COMPLETE for state in asdict(draft.fact_coverage).values()
        ):
            # Four narrative questions never certify an exhaustive finite fact set.
            raise ValueError("Narrative onboarding cannot confirm complete finite-fact coverage.")
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
            structured_preferences=draft.structured_preferences,
            languages=draft.languages,
            licences=draft.licences,
            work_authorizations=draft.work_authorizations,
            fact_coverage=draft.fact_coverage,
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
        need_ids = [need.need_id for need in draft.needs]
        if len(need_ids) != len(set(need_ids)) or any(
            not need.need_id.strip() or not need.label.strip() for need in draft.needs
        ):
            raise ValueError("Job interpretation requires unique named needs.")
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

    def job_profile_from_observation(self, *, job_id, source_repository, user_id=None):
        hard_facts = source_repository.load_job_hard_facts(job_id, user_id=user_id)
        return self.job_profile(hard_facts=hard_facts)
