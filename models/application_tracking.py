from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class ApplicationStage(str, Enum):
    ANALYSED = "analysed"
    READY_TO_APPLY = "ready_to_apply"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    NO_RESPONSE = "no_response"


TERMINAL_APPLICATION_STAGES = {
    ApplicationStage.ACCEPTED,
    ApplicationStage.REJECTED,
    ApplicationStage.DECLINED,
    ApplicationStage.WITHDRAWN,
    ApplicationStage.NO_RESPONSE,
}


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())


def _items(values) -> tuple[str, ...]:
    return tuple(
        _clean(value)
        for value in values or ()
        if _clean(value)
    )


@dataclass(frozen=True)
class InterviewRound:
    interview_id: str
    candidate_id: str
    job_id: str
    sequence: int
    scheduled_at: str
    interviewer_names: tuple[str, ...] = ()
    interviewer_roles: tuple[str, ...] = ()
    interview_type: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        for name in (
            "interview_id",
            "candidate_id",
            "job_id",
            "scheduled_at",
            "interview_type",
            "notes",
            "created_at",
            "updated_at",
        ):
            object.__setattr__(
                self,
                name,
                str(getattr(self, name) or "").strip() if name == "notes" else _clean(getattr(self, name)),
            )
        object.__setattr__(
            self,
            "interviewer_names",
            _items(self.interviewer_names),
        )
        object.__setattr__(
            self,
            "interviewer_roles",
            _items(self.interviewer_roles),
        )
        if (
            not self.interview_id
            or not self.candidate_id
            or not self.job_id
            or self.sequence < 1
        ):
            raise ValueError("Interview round identity is invalid.")
        if self.scheduled_at:
            if datetime.fromisoformat(self.scheduled_at).tzinfo is None:
                raise ValueError("Interview schedule requires a timezone.")


@dataclass(frozen=True)
class InterviewRoundFeedback:
    interview_id: str
    candidate_id: str
    job_id: str
    feedback_text: str = ""
    next_steps: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            object.__setattr__(
                self,
                name,
                str(getattr(self, name) or "").strip() if name in {"feedback_text", "next_steps"} else _clean(getattr(self, name)),
            )
        if (
            not self.interview_id
            or not self.candidate_id
            or not self.job_id
        ):
            raise ValueError("Interview feedback identity is invalid.")
