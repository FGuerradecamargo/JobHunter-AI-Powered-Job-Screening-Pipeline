from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from models.gmail_connection import GmailConnection
from services.database import initialize_database
from services.gmail_connection_repository import (
    GmailConnectionRepository,
)
from services.gmail_oauth_service import GmailOAuthService
from services.oauth_state_repository import (
    OAuthStateRepository,
)
from services.user_repository import UserRepository


load_dotenv()
initialize_database()

st.set_page_config(
    page_title="Connect Gmail",
    page_icon="📧",
    layout="centered",
)

st.title("Connect Gmail")

st.caption(
    "Connect a Gmail account so JobHunter can read "
    "job alert emails."
)


user_repository = UserRepository()
gmail_repository = GmailConnectionRepository()
oauth_state_repository = OAuthStateRepository()
oauth_service = GmailOAuthService()


def get_query_parameter(
    name: str,
) -> str | None:
    value = st.query_params.get(name)

    if value is None:
        return None

    if isinstance(value, list):
        return value[0] if value else None

    return str(value)

    query_string = st.query_params.to_dict()

    if not query_string:
        return redirect_uri

    query_parts = []

    for key, value in query_string.items():
        if isinstance(value, list):
            for item in value:
                query_parts.append(
                    f"{key}={item}"
                )
        else:
            query_parts.append(
                f"{key}={value}"
            )

    return (
        f"{redirect_uri}"
        f"?{'&'.join(query_parts)}"
    )


def handle_oauth_callback() -> None:
    authorization_code = get_query_parameter(
        "code"
    )

    returned_state = get_query_parameter(
        "state"
    )

    oauth_error = get_query_parameter(
        "error"
    )

    oauth_error_description = get_query_parameter(
        "error_description"
    )

    if oauth_error:
        message = (
            "Google authorization was cancelled "
            "or failed."
        )

        if oauth_error_description:
            message += (
                f" Details: "
                f"{oauth_error_description}"
            )

        st.error(message)
        return

    if (
        not authorization_code
        or not returned_state
    ):
        return

    authorization_state = (
        oauth_state_repository.consume(
            returned_state
        )
    )

    if authorization_state is None:
        st.error(
            "The authorization request is invalid, "
            "expired, or has already been used."
        )
        return

    try:
        result = (
            oauth_service
            .exchange_authorization_code(
                authorization_code=(
                    authorization_code
                ),
                expected_state=returned_state,
                code_verifier=(
                    authorization_state.code_verifier
                ),
            )
        )

        gmail_repository.save(
            GmailConnection(
                user_id=(
                    authorization_state.user_id
                ),
                gmail_address=(
                    result.gmail_address
                ),
                refresh_token=(
                    result.refresh_token
                ),
                access_token=(
                    result.access_token
                ),
                token_expiry=(
                    result.token_expiry
                ),
                scopes=result.scopes,
                connection_status="connected",
            )
        )

    except Exception as error:
        st.error(
            "Could not complete Gmail connection."
        )
        st.exception(error)
        return

    st.query_params.clear()

    st.success(
        "Gmail connected successfully: "
        f"{result.gmail_address}"
    )

    st.rerun()


handle_oauth_callback()


users = user_repository.list_all()

if not users:
    st.warning(
        "No application users were found. "
        "Create a user before connecting Gmail."
    )
    st.stop()


user_by_id = {
    user.id: user
    for user in users
}

selected_user_id = st.selectbox(
    "Application user",
    options=list(user_by_id.keys()),
    format_func=lambda user_id: (
        f"{user_by_id[user_id].display_name} "
        f"({user_by_id[user_id].email})"
    ),
)

selected_user = user_by_id[
    selected_user_id
]

existing_connection = (
    gmail_repository.get_by_user_id(
        selected_user.id
    )
)

if existing_connection is not None:
    st.success(
        "Connected Gmail: "
        f"{existing_connection.gmail_address}"
    )

    st.write(
        "Connection status:",
        existing_connection.connection_status,
    )

    if existing_connection.last_sync_at:
        st.write(
            "Last sync:",
            existing_connection.last_sync_at,
        )

    if st.button(
        "Disconnect Gmail",
        use_container_width=True,
    ):
        gmail_repository.disconnect(
            selected_user.id
        )

        st.success(
            "Gmail disconnected successfully."
        )

        st.rerun()

else:
    st.info(
        "This user does not have a Gmail "
        "account connected yet."
    )


if "gmail_authorization_url" not in st.session_state:
    st.session_state[
        "gmail_authorization_url"
    ] = None


if st.button(
    "Connect Gmail",
    type="primary",
    use_container_width=True,
):
    authorization_request = (
        oauth_service.create_authorization_url()
    )

    oauth_state_repository.delete_expired()

    oauth_state_repository.save(
        state=(
            authorization_request.state
        ),
        user_id=selected_user.id,
        code_verifier=(
            authorization_request.code_verifier
        ),
    )

    st.session_state[
        "gmail_authorization_url"
    ] = (
        authorization_request.authorization_url
    )


authorization_url = st.session_state.get(
    "gmail_authorization_url"
)

if authorization_url:
    st.link_button(
        "Continue with Google",
        authorization_url,
        type="primary",
        use_container_width=True,
    )

    st.caption(
        "You will be redirected to Google "
        "to approve read-only Gmail access."
    )