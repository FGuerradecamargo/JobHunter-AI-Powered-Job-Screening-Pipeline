from dataclasses import dataclass


@dataclass
class CandidateConstraints:
    relocation: str = "conditional"
    minimum_salary: int | None = None

    unsupported_languages_are_blocking: bool = True
    night_shift_is_blocking: bool = True
    mandatory_relocation_is_blocking: bool = False

    maximum_onsite_days_per_week: int | None = None