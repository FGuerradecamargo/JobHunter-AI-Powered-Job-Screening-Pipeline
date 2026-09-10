from __future__ import annotations

import streamlit as st

from models.app_user import AppUser
from models.user_context import UserContext
from services.active_user_context_service import (
    ActiveUserContextService,
)
from services.active_user_session import (
    ActiveUserSession,
)


def get_active_user_context(
    *,
    authenticated_user: AppUser,
) -> UserContext:
    return (
        ActiveUserContextService(
            active_user_session=ActiveUserSession(
                st.session_state
            )
        )
        .resolve(
            authenticated_user=authenticated_user
        )
    )


def set_active_user(
    *,
    authenticated_user: AppUser,
    active_user_id: str,
) -> UserContext:
    return (
        ActiveUserContextService(
            active_user_session=ActiveUserSession(
                st.session_state
            )
        )
        .activate(
            authenticated_user=authenticated_user,
            active_user_id=active_user_id,
        )
    )
