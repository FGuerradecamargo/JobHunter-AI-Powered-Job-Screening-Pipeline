from __future__ import annotations

from dataclasses import dataclass

from models.app_user import AppUser


@dataclass(frozen=True)
class UserContext:
    authenticated_user: AppUser
    active_user: AppUser

    @property
    def is_viewing_as(self) -> bool:
        return (
            self.authenticated_user.id
            != self.active_user.id
        )
