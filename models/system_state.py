"""Presentation contracts, never evidence or application outcome authority."""
from dataclasses import dataclass
from enum import Enum


class SearchRunState(str, Enum):
    STARTING = "starting"
    SEARCHING = "searching"
    STOPPED = "stopped"
    COMPLETED = "completed"
    NOTHING_WORTHWHILE = "nothing_worthwhile"
    ERROR = "error"


class SystemNoticeKind(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    ATTENTION = "attention"
    ERROR = "error"


@dataclass(frozen=True)
class SystemNotice:
    code: str
    title: str
    message: str
    kind: SystemNoticeKind
    primary_action: str = ""
    secondary_action: str = ""


@dataclass(frozen=True)
class ApplicationAgeState:
    days_since_applied: int
    band: str
    title: str
    action_prompt: str = ""
