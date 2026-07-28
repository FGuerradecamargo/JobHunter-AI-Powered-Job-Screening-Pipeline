from dataclasses import dataclass


@dataclass
class CandidatePreferences:
    remote_allowed: bool = True
    hybrid_allowed: bool = True
    onsite_allowed: bool = False

    weekend_work_allowed: bool = True
    night_shift_allowed: bool = False
    on_call_allowed: bool = False

    customer_facing_preference: str = "limited"
    phone_support_preference: str = "limited"
    sales_adjacent_allowed: bool = False

    preferred_work_schedule: str = "flexible"