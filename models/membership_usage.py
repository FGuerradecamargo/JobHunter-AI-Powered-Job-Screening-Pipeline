from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MembershipUsageResult:
    status: str
    user_id: str
    capability: str
    allowed: bool
    used: int
    limit: int | None
    remaining: int | None
    window: str
    window_start: str = ""
    window_end: str = ""
    event_id: str = ""
    reason: str = ""
