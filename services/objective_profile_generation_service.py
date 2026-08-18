from models.candidate import Candidate
from models.career_objective import CareerObjective
from models.objective_profile import ObjectiveProfile
from services.ai.llm_client import LLMClient
from services.ai.objective_profile_prompt_builder import (
    build_objective_profile_prompt,
)
from services.ai.objective_profile_parser import (
    parse_objective_profile_response,
)
from services.objective_profile_repository import (
    ObjectiveProfileRepository,
)


class ObjectiveProfileGenerationService:
    def __init__(
        self,
        llm_client: LLMClient,
        repository: ObjectiveProfileRepository | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.repository = (
            repository
            or ObjectiveProfileRepository()
        )

    def generate(
        self,
        candidate: Candidate,
        objective: CareerObjective,
    ) -> ObjectiveProfile:
        prompt = build_objective_profile_prompt(
            candidate=candidate,
            objective=objective,
        )

        raw_response = self.llm_client.generate(
            prompt
        )

        data = parse_objective_profile_response(
            raw_response
        )

        relevant_experience_ids = set(
            data[
                "relevant_experience_ids"
            ]
        )

        relevant_experiences = [
            experience
            for experience
            in candidate.professional_experiences
            if experience.source_experience_id
            in relevant_experience_ids
        ]

        profile = ObjectiveProfile(
            candidate_id=candidate.id,
            objective_id=objective.id,
            objective_title=objective.title,
            objective_description=(
                objective.description
            ),
            competitive_role_families=list(
                data[
                    "competitive_role_families"
                ]
            ),
            bridge_role_families=list(
                data[
                    "bridge_role_families"
                ]
            ),
            target_role_families=list(
                data[
                    "target_role_families"
                ]
            ),
            relevant_proven_capabilities=list(
                data[
                    "relevant_proven_capabilities"
                ]
            ),
            relevant_transferable_capabilities=list(
                data[
                    "relevant_transferable_capabilities"
                ]
            ),
            relevant_developing_capabilities=list(
                data[
                    "relevant_developing_capabilities"
                ]
            ),
            relevant_tools=list(
                data[
                    "relevant_tools"
                ]
            ),
            relevant_domains=list(
                data[
                    "relevant_domains"
                ]
            ),
            relevant_strengths=list(
                data[
                    "relevant_strengths"
                ]
            ),
            relevant_experiences=(
                relevant_experiences
            ),
            development_gaps=list(
                data[
                    "development_gaps"
                ]
            ),
            development_priorities=list(
                data[
                    "development_priorities"
                ]
            ),
        )

        self.repository.save(
            profile
        )

        return profile
