from models.candidate import Candidate
from models.candidate_profile import CandidateProfile
from models.career_objective import CareerObjective
from models.career_update import CareerUpdate


def candidate_to_profile(
    candidate: Candidate,
    career_objective: CareerObjective | None = None,
    career_updates: list[CareerUpdate] | None = None,
) -> CandidateProfile:
    positive_preferences: list[str] = []
    negative_preferences: list[str] = []
    hard_constraints: list[str] = []

    positive_priorities: list[str] = []
    negative_priorities: list[str] = []

    preferences = candidate.preferences
    constraints = candidate.constraints

    for priority in candidate.priorities:
        if not priority.active:
            continue

        if priority.direction == "negative":
            negative_priorities.append(
                priority.text
            )
        else:
            positive_priorities.append(
                priority.text
            )

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

    if constraints.unsupported_languages_are_blocking:
        hard_constraints.append(
            "A mandatory language not spoken by the "
            "candidate is a blocking conflict."
        )

    if not preferences.on_call_allowed:
        hard_constraints.append(
            "Mandatory overnight on-call work is not acceptable."
        )

    if constraints.mandatory_relocation_is_blocking:
        hard_constraints.append(
            "Mandatory relocation is a blocking conflict."
        )

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

    bridge_roles = (
        list(candidate.bridge_role_families)
        if candidate.bridge_role_families
        else list(candidate.target_roles)
    )

    target_roles = (
        list(candidate.target_role_families)
        if candidate.target_role_families
        else list(candidate.target_roles)
    )

    current_roles = (
        list(candidate.competitive_role_families)
        if candidate.competitive_role_families
        else [candidate.current_role]
    )

    current_skills = (
        list(candidate.proven_capabilities)
        if candidate.proven_capabilities
        else list(candidate.skills)
    )

    growth_skills = (
        list(candidate.developing_capabilities)
        if candidate.developing_capabilities
        else list(candidate.development_areas)
    )

    professional_experiences = list(
        candidate.professional_experiences
    )

    proven_capabilities = list(
        candidate.proven_capabilities
    )

    transferable_capabilities = list(
        candidate.transferable_capabilities
    )

    developing_capabilities = list(
        candidate.developing_capabilities
    )

    technical_tools = list(
        candidate.technical_tools
    )

    domain_experience = list(
        candidate.domain_experience
    )

    competitive_role_families = list(
        candidate.competitive_role_families
    )

    bridge_role_families = list(
        candidate.bridge_role_families
    )

    target_role_families = list(
        candidate.target_role_families
    )

    strengths = list(
        candidate.strengths
    )

    professional_summary = (
        candidate.professional_summary
    )

    career_objective_title = ""
    career_objective_description = ""

    if career_objective is not None:
        career_objective_title = (
            career_objective.title
        )

        career_objective_description = (
            career_objective.description
        )
        professional_summary += (
            "\n\nCURRENT CAREER OBJECTIVE:\n"
            + career_objective.title
            + "\n"
            + career_objective.description
        )

        if career_objective.desired_role_families:
            target_roles = list(
                career_objective.desired_role_families
            )

            target_role_families = list(
                career_objective.desired_role_families
            )

    return CandidateProfile(
        current_roles=current_roles,
        bridge_roles=bridge_roles,
        target_roles=target_roles,
        current_skills=current_skills,
        growth_skills=growth_skills,
        current_level=candidate.current_level,
        professional_summary=professional_summary,
        job_search_urgency="selective",

        career_objective_title=(
            career_objective_title
        ),
        career_objective_description=(
            career_objective_description
        ),

        professional_experiences=(
            professional_experiences
        ),
        proven_capabilities=(
            proven_capabilities
        ),
        transferable_capabilities=(
            transferable_capabilities
        ),
        developing_capabilities=(
            developing_capabilities
        ),
        technical_tools=technical_tools,
        domain_experience=domain_experience,
        competitive_role_families=(
            competitive_role_families
        ),
        bridge_role_families=(
            bridge_role_families
        ),
        target_role_families=(
            target_role_families
        ),
        strengths=strengths,

        career_updates=[
            (
                update.update_type
                + ": "
                + update.description
            )
            for update in (
                career_updates or []
            )
        ],

        positive_preferences=positive_preferences,
        negative_preferences=negative_preferences,
        hard_constraints=hard_constraints,
        positive_priorities=positive_priorities,
        negative_priorities=negative_priorities,
        relocation_policy=constraints.relocation,
        salary_policy=salary_policy,
        spoken_languages=list(
            candidate.spoken_languages
        ),
    )
