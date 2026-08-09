from models.candidate import Candidate
from models.candidate_constraints import CandidateConstraints
from models.candidate_preferences import CandidatePreferences
from services.ai.candidate_profile_parser import (
    parse_candidate_profile_response,
)
from services.ai.candidate_profile_prompt_builder import (
    build_candidate_profile_prompt,
)
from services.ai.llm_client import LLMClient
from services.candidate_onboarding_repository import (
    CandidateOnboardingRepository,
)
from services.candidate_repository import CandidateRepository


class CandidateProfileGenerationService:
    def __init__(
        self,
        llm_client: LLMClient,
        onboarding_repository: CandidateOnboardingRepository,
        candidate_repository: CandidateRepository,
    ) -> None:
        self.llm_client = llm_client
        self.onboarding_repository = onboarding_repository
        self.candidate_repository = candidate_repository

    def generate(
        self,
        candidate_id: str,
        candidate_name: str,
    ) -> Candidate:
        onboarding = (
            self.onboarding_repository.get_onboarding(
                candidate_id
            )
        )

        if onboarding is None:
            raise ValueError(
                "Candidate onboarding was not found."
            )

        experiences = (
            self.onboarding_repository.list_work_experiences(
                candidate_id
            )
        )

        if not experiences:
            raise ValueError(
                "At least one work experience is required."
            )

        prompt = build_candidate_profile_prompt(
            onboarding=onboarding,
            experiences=experiences,
        )

        raw_response = self.llm_client.generate(
            prompt
        )

        profile_data = (
            parse_candidate_profile_response(
                raw_response
            )
        )

        existing_candidate = (
            self.candidate_repository.get(
                candidate_id
            )
        )

        preferences = (
            existing_candidate.preferences
            if existing_candidate
            else CandidatePreferences()
        )

        constraints = (
            existing_candidate.constraints
            if existing_candidate
            else CandidateConstraints()
        )

        candidate = Candidate(
            id=candidate_id,
            name=candidate_name,
            current_role=profile_data[
                "current_role"
            ],
            current_level=profile_data[
                "current_level"
            ],
            professional_summary=profile_data[
                "professional_summary"
            ],
            target_roles=profile_data[
                "target_roles"
            ],
            spoken_languages=list(
                onboarding.spoken_languages
            ),
            skills=profile_data[
                "skills"
            ],
            strengths=profile_data[
                "strengths"
            ],
            development_areas=profile_data[
                "development_areas"
            ],
            preferences=preferences,
            constraints=constraints,
        )

        self.candidate_repository.save(
            candidate
        )

        return candidate
