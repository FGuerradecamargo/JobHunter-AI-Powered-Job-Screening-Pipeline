"""Composition of Candidate Profile behavior and the existing onboarding port."""
from dataclasses import dataclass

from services.candidate_profile_generation_service import CandidateProfileGenerationService
from services.candidate_profile_service import CandidateProfileService
from services.candidate_profile_priority_service import CandidateProfilePriorityService
from services.profile_gateway import CandidateProfileGateway, ProfileGateway
from services.profile_readiness_service import ProfileReadinessService
from services.profile_snapshot_repository import ProfileSnapshotRepository


class _OnDemandProfileClient:
    def generate(self, prompt):
        from services.ai.openai_client import OpenAIClient

        return OpenAIClient().generate(prompt)


@dataclass(frozen=True)
class CandidateProfileRuntime:
    service: CandidateProfileService
    onboarding_gateway: ProfileGateway
    priorities: CandidateProfilePriorityService


def create_candidate_profile_runtime(
    *, onboarding_repository, career_update_repository, candidate_repository,
) -> CandidateProfileRuntime:
    snapshots = ProfileSnapshotRepository()
    generation = CandidateProfileGenerationService(
        llm_client=_OnDemandProfileClient(), onboarding_repository=onboarding_repository,
        candidate_repository=candidate_repository, career_update_repository=career_update_repository,
        snapshot_repository=snapshots,
    )
    readiness = ProfileReadinessService(snapshots=snapshots, onboarding=onboarding_repository,
                                        updates=career_update_repository)
    return CandidateProfileRuntime(
        service=CandidateProfileService(snapshot_repository=snapshots,
            readiness_service=readiness, generation_service=generation),
        onboarding_gateway=CandidateProfileGateway(generation),
        priorities=CandidateProfilePriorityService(candidate_repository),
    )
