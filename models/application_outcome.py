from dataclasses import dataclass


@dataclass
class ApplicationOutcome:
    candidate_id: str
    job_id: str

    final_status: str = ""
    interview_stage: str = ""
    rejection_reason: str = ""
    recruiter_feedback: str = ""
    candidate_notes: str = ""

    offer_salary: str = ""
    offer_currency: str = ""

    lessons_learned: str = ""

    outcome_date: str = ""
    created_at: str = ""
    updated_at: str = ""
