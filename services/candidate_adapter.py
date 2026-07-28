from models.candidate import Candidate
from models.candidate_profile import CandidateProfile


def candidate_to_profile(
    candidate: Candidate,
) -> CandidateProfile:
    positive_preferences: list[str] = []
    negative_preferences: list[str] = []
    hard_constraints: list[str] = []

    preferences = candidate.preferences
    constraints = candidate.constraints

    if preferences.remote_allowed:
        positive_preferences.append(
            "Remote work is preferred or acceptable."
        )

    if preferences.hybrid_allowed:
        positive_preferences.append(
            "Hybrid work is acceptable."
        )

    if preferences.weekend_work_allowed:
        positive_preferences.append(
            "Weekend daytime work is acceptable."
        )

    if not preferences.onsite_allowed:
        negative_preferences.append(
            "Fully onsite work is undesirable."
        )

    if (
        preferences.customer_facing_preference
        == "limited"
    ):
        negative_preferences.append(
            "High external customer interaction is undesirable."
        )

    if (
        preferences.phone_support_preference
        == "limited"
    ):
        negative_preferences.append(
            "Phone-heavy support is undesirable."
        )

    if not preferences.sales_adjacent_allowed:
        negative_preferences.append(
            "Sales-adjacent and account-management work "
            "is undesirable."
        )

    if (
        constraints.night_shift_is_blocking
        or not preferences.night_shift_allowed
    ):
        hard_constraints.append(
            "Night and overnight shifts are not acceptable."
        )

    if (
        constraints.unsupported_languages_are_blocking
    ):
        hard_constraints.append(
            "A mandatory language not spoken by the "
            "candidate is a blocking conflict."
        )

    if not preferences.on_call_allowed:
        hard_constraints.append(
            "Mandatory overnight on-call work is not acceptable."
        )

    if (
        constraints.mandatory_relocation_is_blocking
    ):
        hard_constraints.append(
            "Mandatory relocation is a blocking conflict."
        )

    salary_policy = ""

    if constraints.minimum_salary is not None:
        salary_policy = (
            "Minimum acceptable annual salary: "
            f"{constraints.minimum_salary}."
        )
    else:
        salary_policy = (
            "Salary must represent a meaningful improvement "
            "or justify the career opportunity."
        )

    return CandidateProfile(
        current_roles=[
            candidate.current_role,
        ],
        bridge_roles=list(
            candidate.target_roles
        ),
        target_roles=list(
            candidate.target_roles
        ),
        current_skills=list(
            candidate.skills
        ),
        growth_skills=list(
            candidate.development_areas
        ),
        current_level=candidate.current_level,
        professional_summary=(
            candidate.professional_summary
        ),
        job_search_urgency="selective",
        positive_preferences=positive_preferences,
        negative_preferences=negative_preferences,
        hard_constraints=hard_constraints,
        relocation_policy=constraints.relocation,
        salary_policy=salary_policy,
        spoken_languages=list(
            candidate.spoken_languages
        ),
    )