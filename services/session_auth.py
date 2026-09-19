from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

from models.app_user import AppUser
from services.application_bootstrap import (
    bootstrap_application,
)
from services.database import get_connection
from services.session_store import (
    ensure_session_table_with_connection,
    revoke_user_sessions_with_connection,
)
from services.user_repository import UserRepository


SESSION_COOKIE = "jobhunter_session"
SESSION_DAYS = 7
SESSION_IDLE_MINUTES = 60
SESSION_EXPIRED_NOTICE = (
    "Your session expired due to inactivity. "
    "Please log in again."
)


bootstrap_application()


def _resolve_session_cookie_key() -> str:
    environment_value = str(
        os.getenv("SESSION_COOKIE_KEY") or ""
    ).strip()

    if environment_value:
        return environment_value

    try:
        streamlit_value = st.secrets.get(
            "SESSION_COOKIE_KEY"
        )
    except Exception:
        streamlit_value = None

    resolved_value = str(
        streamlit_value or ""
    ).strip()

    if not resolved_value:
        raise RuntimeError(
            "SESSION_COOKIE_KEY is not configured."
        )

    return resolved_value


SESSION_COOKIE_KEY = _resolve_session_cookie_key()


cookies = EncryptedCookieManager(
    prefix="jobhunter_",
    password=SESSION_COOKIE_KEY,
)

if not cookies.ready():
    st.stop()


def _hash_session_token(
    token: str,
) -> str:
    normalized_token = str(
        token or ""
    ).strip()

    if not normalized_token:
        raise ValueError(
            "Session token cannot be empty."
        )

    return hashlib.sha256(
        normalized_token.encode("utf-8")
    ).hexdigest()


def ensure_session_table() -> None:
    with get_connection() as connection:
        ensure_session_table_with_connection(
            connection
        )


def _utc_now_datetime() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value or ""))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clear_local_session() -> None:
    for key in (
        "opportunity_search_run", "scan_requested", "scan_in_progress",
        "last_scan_result", "last_scan_total", "last_links_created",
        "last_scan_target", "last_pool_remaining",
    ):
        st.session_state.pop(key, None)
    cookies[SESSION_COOKIE] = ""
    cookies.save()
    st.session_state.pop("current_user", None)
    st.session_state.pop("active_user_id", None)
    st.session_state.pop("active_user_owner_id", None)
    for key in list(st.session_state):
        if str(key).startswith(("admin_viewing_as_", "admin_access_", "_voice_", "onboarding_step_")):
            st.session_state.pop(key, None)
    st.session_state["reauthentication_required"] = True


def _expire_local_session() -> None:
    _clear_local_session()
    st.session_state["authentication_notice"] = (
        SESSION_EXPIRED_NOTICE
    )


def get_authenticated_user() -> AppUser | None:
    ensure_session_table()

    token = cookies.get(
        SESSION_COOKIE
    )

    if not token:
        st.session_state.pop(
            "current_user",
            None,
        )
        return None

    token_hash = _hash_session_token(
        token
    )

    now = _utc_now_datetime()
    session_expired = False

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                user_id,
                expires_at,
                created_at,
                last_activity_at
            FROM user_sessions
            WHERE token = ?
            """,
            (token_hash,),
        ).fetchone()

        if row is not None:
            try:
                expires_at = _parse_utc_datetime(
                    row["expires_at"]
                )
                last_activity_at = _parse_utc_datetime(
                    row["last_activity_at"]
                    or row["created_at"]
                )
                session_expired = (
                    expires_at <= now
                    or now - last_activity_at
                    > timedelta(
                        minutes=SESSION_IDLE_MINUTES
                    )
                )
            except (TypeError, ValueError):
                session_expired = True

            if session_expired:
                connection.execute(
                    "DELETE FROM user_sessions WHERE token = ?",
                    (token_hash,),
                )
            else:
                connection.execute(
                    """
                    UPDATE user_sessions
                    SET last_activity_at = ?
                    WHERE token = ?
                    """,
                    (now.isoformat(), token_hash),
                )

    if row is None:
        logout_user()
        return None

    if session_expired:
        _expire_local_session()
        return None

    user = UserRepository().get_by_id(
        row["user_id"]
    )

    if user is None:
        logout_user()
        return None

    st.session_state.current_user = user

    return user


def get_current_user() -> AppUser | None:
    """
    Backward-compatible alias.

    New code should use get_authenticated_user()
    when referring to the identity that actually
    owns the WorkPilot session.
    """
    return get_authenticated_user()


def login_user(
    user: AppUser,
) -> None:
    ensure_session_table()

    token = secrets.token_urlsafe(48)

    token_hash = _hash_session_token(
        token
    )

    now = _utc_now_datetime()
    created_at = now.isoformat()
    expires_at = (
        now
        + timedelta(days=SESSION_DAYS)
    ).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_sessions (
                token,
                user_id,
                expires_at,
                created_at,
                last_activity_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                token_hash,
                user.id,
                expires_at,
                created_at,
                created_at,
            ),
        )

    cookies[SESSION_COOKIE] = token
    cookies.save()

    st.session_state.pop("reauthentication_required", None)
    st.session_state.pop("authentication_notice", None)
    st.session_state.current_user = user


def revoke_user_sessions(
    user_id: str,
) -> int:
    normalized_user_id = str(
        user_id or ""
    ).strip()

    if not normalized_user_id:
        raise ValueError(
            "User ID is required."
        )

    with get_connection() as connection:
        return revoke_user_sessions_with_connection(
            connection,
            normalized_user_id,
        )


def logout_user() -> None:
    token = cookies.get(
        SESSION_COOKIE
    )

    if token:
        token_hash = _hash_session_token(
            token
        )

        with get_connection() as connection:
            connection.execute(
                """
                DELETE FROM user_sessions
                WHERE token = ?
                """,
                (token_hash,),
            )

    _clear_local_session()

    for key in list(
        st.session_state.keys()
    ):
        if str(key).startswith((
            "admin_viewing_as_",
            "admin_access_",
        )):
            st.session_state.pop(
                key,
                None,
            )


def require_authenticated_user() -> AppUser:
    user = get_authenticated_user()

    if user is None:
        st.warning(st.session_state.pop(
            "authentication_notice",
            "Please log in to continue.",
        ))

        st.page_link(
            "pages/0_Login.py",
            label="Go to login",
        )

        st.stop()

    return user


def require_login() -> AppUser:
    """
    Backward-compatible alias.

    New code should use
    require_authenticated_user().
    """
    return require_authenticated_user()


def render_logout_button() -> None:
    user = get_authenticated_user()

    if user is None:
        return

    with st.sidebar:
        st.caption(
            f"Signed in as {user.display_name}"
        )

        if st.button(
            "Log out",
            use_container_width=True,
            key="global_logout_button",
        ):
            logout_user()

            if st.user.is_logged_in:
                st.logout()

            st.rerun()

