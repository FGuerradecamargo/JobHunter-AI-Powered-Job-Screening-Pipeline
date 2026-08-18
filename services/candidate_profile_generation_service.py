from models.candidate import Candidate
from models.candidate_constraints import CandidateConstraints
from models.candidate_preferences import CandidatePreferences
from models.professional_experience_profile import (
    ProfessionalExperienceProfile,
)
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
from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.career_objective_repository import (
    CareerObjectiveRepository,
)
from services.objective_profile_generation_service import (
    ObjectiveProfileGenerationService,
)


class CandidateProfileGenerationService:
    def __init__(
        self,
        llm_client: LLMClient,
        onboarding_repository: CandidateOnboardingRepository,
        candidate_repository: CandidateRepository,
        career_update_repository: CareerUpdateRepository,
        career_objective_repository: (
            CareerObjectiveRepository | None
        ) = None,
        objective_profile_generation_service: (
            ObjectiveProfileGenerationService | None
        ) = None,
    ) -> None:
        self.llm_client = llm_client
        self.onboarding_repository = onboarding_repository
        self.candidate_repository = candidate_repository
        self.career_update_repository = (
            career_update_repository
        )
        self.career_objective_repository = (
            career_objective_repository
            or CareerObjectiveRepository()
        )
        self.objective_profile_generation_service = (
            objective_profile_generation_service
            or ObjectiveProfileGenerationService(
                llm_client=llm_client
            )
        )

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

        career_updates = (
            self.career_update_repository
            .list_for_candidate(
                candidate_id
            )
        )

        prompt = build_candidate_profile_prompt(
            onboarding=onboarding,
            experiences=experiences,
            career_updates=career_updates,
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

        priorities = (
            list(existing_candidate.priorities)
            if existing_candidate
            else []
        )

        professional_experiences = [
            ProfessionalExperienceProfile(
                source_experience_id=item[
                    "source_experience_id"
                ],
                company=item[
                    "company"
                ],
                stated_role=item[
                    "stated_role"
                ],
                inferred_role=item[
                    "inferred_role"
                ],
                role_family=item[
                    "role_family"
                ],
                summary=item[
                    "summary"
                ],
                responsibilities=list(
                    item["responsibilities"]
                ),
                demonstrated_capabilities=list(
                    item[
                        "demonstrated_capabilities"
                    ]
                ),
                transferable_capabilities=list(
                    item[
                        "transferable_capabilities"
                    ]
                ),
                tools=list(
                    item["tools"]
                ),
                domains=list(
                    item["domains"]
                ),
                evidence=list(
                    item["evidence"]
                ),
            )
            for item in profile_data[
                "professional_experiences"
            ]
        ]

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
            target_roles=list(
                profile_data[
                    "target_roles"
                ]
            ),
            spoken_languages=list(
                onboarding.spoken_languages
            ),
            skills=list(
                profile_data[
                    "skills"
                ]
            ),
            strengths=list(
                profile_data[
                    "strengths"
                ]
            ),
            development_areas=list(
                profile_data[
                    "development_areas"
                ]
            ),
            professional_experiences=(
                professional_experiences
            ),
            proven_capabilities=list(
                profile_data[
                    "proven_capabilities"
                ]
            ),
            transferable_capabilities=list(
                profile_data[
                    "transferable_capabilities"
                ]
            ),
            developing_capabilities=list(
                profile_data[
                    "developing_capabilities"
                ]
            ),
            technical_tools=list(
                profile_data[
                    "technical_tools"
                ]
            ),
            domain_experience=list(
                profile_data[
                    "domain_experience"
                ]
            ),
            competitive_role_families=list(
                profile_data[
                    "competitive_role_families"
                ]
            ),
            bridge_role_families=list(
                profile_data[
                    "bridge_role_families"
                ]
            ),
            target_role_families=list(
                profile_data[
                    "target_role_families"
                ]
            ),
            preferences=preferences,
            constraints=constraints,
            priorities=priorities,
        )

        self.candidate_repository.save(
            candidate
        )

        active_objective = (
            self.career_objective_repository
            .get_active(
                candidate_id
            )
        )

        if active_objective is not None:
            (
                self.objective_profile_generation_service
                .generate(
                    candidate=candidate,
                    objective=active_objective,
                )
            )

        return candidate
