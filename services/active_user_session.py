from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


ACTIVE_USER_ID_KEY = "active_user_id"
ACTIVE_USER_OWNER_ID_KEY = "active_user_owner_id"


class ActiveUserSession:
    def __init__(
        self,
        state: MutableMapping[str, Any],
    ) -> None:
        self.state = state

    def get_active_user_id(
        self,
        *,
        authenticated_user_id: str,
    ) -> str | None:
        owner_id = str(
            self.state.get(
                ACTIVE_USER_OWNER_ID_KEY,
                "",
            )
            or ""
        ).strip()

        if owner_id != authenticated_user_id:
            self.state[
                ACTIVE_USER_OWNER_ID_KEY
            ] = authenticated_user_id

            self.state.pop(
                ACTIVE_USER_ID_KEY,
                None,
            )

            return None

        active_user_id = str(
            self.state.get(
                ACTIVE_USER_ID_KEY,
                "",
            )
            or ""
        ).strip()

        return (
            active_user_id
            if active_user_id
            else None
        )

    def set_active_user_id(
        self,
        *,
        authenticated_user_id: str,
        active_user_id: str,
    ) -> None:
        normalized_active_user_id = str(
            active_user_id
        ).strip()

        if not normalized_active_user_id:
            raise ValueError(
                "Active user id is required."
            )

        self.state[
            ACTIVE_USER_OWNER_ID_KEY
        ] = authenticated_user_id

        self.state[
            ACTIVE_USER_ID_KEY
        ] = normalized_active_user_id

    def reset(
        self,
        *,
        authenticated_user_id: str,
    ) -> None:
        self.state[
            ACTIVE_USER_OWNER_ID_KEY
        ] = authenticated_user_id

        self.state.pop(
            ACTIVE_USER_ID_KEY,
            None,
        )
