from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppUser:
    id: str
    email: str
    display_name: str
    candidate_id: Optional[str] = None