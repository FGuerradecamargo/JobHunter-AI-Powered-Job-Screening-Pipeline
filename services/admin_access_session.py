from collections.abc import MutableMapping
from typing import Any


ADMIN_ACCESS_GRANT_PREFIX = "admin_access_grant_"


class AdminAccessSession:
    def __init__(
        self,
        state: MutableMapping[str, Any],
    ) -> None:
        self.state = state

    @staticmethod
    def _key(authenticated_user_id: str) -> str:
        return (
            ADMIN_ACCESS_GRANT_PREFIX
            + authenticated_user_id
        )

    def get_authorized_target(
        self,
        *,
        authenticated_user_id: str,
    ) -> str | None:
        target_id = str(
            self.state.get(
                self._key(authenticated_user_id),
                "",
            )
            or ""
        ).strip()

        return target_id or None

    def authorize(
        self,
        *,
        authenticated_user_id: str,
        target_user_id: str,
    ) -> None:
        normalized_target_id = str(
            target_user_id or ""
        ).strip()

        if not normalized_target_id:
            raise ValueError("Target user ID is required.")

        if normalized_target_id == authenticated_user_id:
            raise ValueError(
                "Administrative access must target another user."
            )

        self.state[
            self._key(authenticated_user_id)
        ] = normalized_target_id

    def reset(
        self,
        *,
        authenticated_user_id: str,
    ) -> None:
        self.state.pop(
            self._key(authenticated_user_id),
            None,
        )
