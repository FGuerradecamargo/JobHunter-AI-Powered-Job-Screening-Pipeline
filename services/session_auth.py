from datetime import datetime, timedelta, timezone
import secrets

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

from models.app_user import AppUser
from services.database import get_connection, utc_now
from services.user_repository import UserRepository


SESSION_COOKIE = "jobhunter_session"
SESSION_DAYS = 7


cookies = EncryptedCookieManager(
    prefix="jobhunter_",
    password="jobhunter-beta-cookie-key",
)

if not cookies.ready():
    st.stop()


def ensure_session_table() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )


def get_current_user() -> AppUser | None:
    user = st.session_state.get(
        "current_user"
    )

    if user is not None:
        return user

    ensure_session_table()

    token = cookies.get(
        SESSION_COOKIE
    )

    if not token:
        return None

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                user_id,
                expires_at
            FROM user_sessions
            WHERE token = %s
            """,
            (token,),
        ).fetchone()

    if row is None:
        return None

    expires_at = datetime.fromisoformat(
        row["expires_at"]
    )

    if expires_at < datetime.now(timezone.utc):
        logout_user()
        return None

    user = UserRepository().get_by_id(
        row["user_id"]
    )

    if user is None:
        logout_user()
        return None

    st.session_state.current_user = user

    return user


def login_user(
    user: AppUser,
) -> None:
    ensure_session_table()

    token = secrets.token_urlsafe(48)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=SESSION_DAYS)
    ).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_sessions (
                token,
                user_id,
                expires_at,
                created_at
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                token,
                user.id,
                expires_at,
                utc_now(),
            ),
        )

    cookies[SESSION_COOKIE] = token
    cookies.save()

    st.session_state.current_user = user


def logout_user() -> None:
    token = cookies.get(
        SESSION_COOKIE
    )

    if token:
        with get_connection() as connection:
            connection.execute(
                """
                DELETE FROM user_sessions
                WHERE token = %s
                """,
                (token,),
            )

    cookies[SESSION_COOKIE] = ""
    cookies.save()

    if "current_user" in st.session_state:
        del st.session_state["current_user"]


def require_login() -> AppUser:
    user = get_current_user()

    if user is None:
        st.warning(
            "Please log in to continue."
        )

        st.page_link(
            "pages/0_Login.py",
            label="Go to login",
        )

        st.stop()

    return user


def render_logout_button() -> None:
    user = get_current_user()

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

            st.switch_page(
                "pages/0_Login.py"
            )
