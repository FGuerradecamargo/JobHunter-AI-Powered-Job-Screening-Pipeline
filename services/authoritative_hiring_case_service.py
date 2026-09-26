from __future__ import annotations

from models.hiring_case import HiringCase, RequirementAssessment
from models.profile_interpretation import (
    AIJobProfileSnapshot,
    CandidateProfileSnapshot,
    JobHardFacts,
)
from services.hiring_case_engine import build_hiring_case
from services.profile_hiring_case_adapter import build_profile_hiring_case_input
from services.profile_interpreter import ProfileInterpreter


class AuthoritativeHiringCaseService:
    """
    Official Candidate <-> Job evaluator for WorkPilot V1.

    This path does not read or compare legacy recommendation buckets. The
    interpreter may propose grounded relationships, but the deterministic
    adapter + HiringCase engine remain authoritative for the final result.
    """

    def __init__(self, interpreter: ProfileInterpreter) -> None:
        self.interpreter = interpreter

    def evaluate(
        self,
        *,
        candidate_profile: CandidateProfileSnapshot,
        job_profile: AIJobProfileSnapshot,
        hard_facts: JobHardFacts,
        hard_assessments: tuple[RequirementAssessment, ...] = (),
    ) -> HiringCase:
        if job_profile.job_id != hard_facts.job_id:
            raise PermissionError(
                "Job profile and hard facts are not scoped to the same job."
            )
        if job_profile.job_signature != hard_facts.job_signature:
            raise ValueError(
                "Job profile is stale for the supplied hard facts."
            )

        interpretation = self.interpreter.analyze_hiring_case(
            candidate_profile=candidate_profile,
            job_profile=job_profile,
        )

        data = build_profile_hiring_case_input(
            candidate_profile=candidate_profile,
            job_profile=job_profile,
            hard_facts=hard_facts,
            interpretation=interpretation,
            hard_assessments=hard_assessments,
        )

        return build_hiring_case(data)
