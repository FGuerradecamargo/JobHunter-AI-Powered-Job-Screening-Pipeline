from __future__ import annotations

import logging
import hashlib
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

import streamlit as st
from dotenv import load_dotenv

import os

from models.gmail_connection import GmailConnection
from models.job import Job
from services.database import (
    initialize_database,
    upsert_raw_job,
)
from services.job_source_repository import JobSourceRepository
from services.gmail_message_repository import GmailMessageRepository
from services.gmail_job_processor import GmailJobProcessor
from services.gmail_sync_service import GmailSyncService
from services.gmail_connection_repository import (
    GmailConnectionRepository,
)
from services.gmail_oauth_service import GmailOAuthService
from services.oauth_state_repository import (
    OAuthStateRepository,
)
from services.user_repository import UserRepository

import os
import streamlit as st

client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")

st.caption(
    "OAuth Client ID loaded: "
    + (
        f"{client_id[:12]}...{client_id[-12:]}"
        if client_id
        else "NOT SET"
    )
)

load_dotenv()
initialize_database()

st.set_page_config(
    page_title="Sources",
    page_icon="📧",
    layout="centered",
)

st.title("Sources")

st.caption(
    "Manage where JobHunter gets opportunities from."
)

st.subheader("Gmail job alerts")

st.caption(
    "Connect Gmail so JobHunter can import supported "
    "job alert emails automatically."
)


user_repository = UserRepository()
gmail_repository = GmailConnectionRepository()
oauth_state_repository = OAuthStateRepository()
oauth_service = GmailOAuthService()
job_source_repository = JobSourceRepository()
gmail_message_repository = GmailMessageRepository()
gmail_job_processor = GmailJobProcessor(
    gmail_message_repository=gmail_message_repository
)
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
        logger.exception("Could not complete Gmail connection.")
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


# =========================================================
# GMAIL SYNC
# =========================================================

st.divider()
st.subheader("Gmail sync")

existing_connection = (
    gmail_repository.get_by_user_id(
        selected_user.id
    )
)

if (
    existing_connection is not None
    and existing_connection.connection_status
    == "connected"
):
    st.caption(
        f"Connected: "
        f"{existing_connection.gmail_address}"
    )

    if existing_connection.last_sync_at:
        st.caption(
            f"Last sync: "
            f"{existing_connection.last_sync_at}"
        )

    if st.button(
        "Sync Gmail now",
        type="secondary",
        use_container_width=True,
        key="sources_sync_gmail",
    ):
        try:
            gmail_sync_service = GmailSyncService(
                client_id=os.environ[
                    "GOOGLE_OAUTH_CLIENT_ID"
                ],
                client_secret=os.environ[
                    "GOOGLE_OAUTH_CLIENT_SECRET"
                ],
                gmail_connection_repository=(
                    gmail_repository
                ),
                gmail_message_repository=(
                    gmail_message_repository
                ),
            )

            with st.spinner(
                "Checking Gmail for job alerts..."
            ):
                sync_result = (
                    gmail_sync_service
                    .sync_recent_job_alerts(
                        user_id=selected_user.id
                    )
                )

                processing_result = (
                    gmail_job_processor
                    .process_pending_messages(
                        user_id=selected_user.id,
                        limit=100,
                    )
                )

            st.success(
                "Gmail sync completed."
            )

            sync_columns = st.columns(4)

            sync_columns[0].metric(
                "Emails found",
                sync_result.total_messages_found,
            )

            sync_columns[1].metric(
                "New emails",
                sync_result.new_messages_found,
            )

            sync_columns[2].metric(
                "Jobs added",
                processing_result.jobs_created,
            )

            sync_columns[3].metric(
                "Already known",
                processing_result.jobs_unchanged,
            )

        except Exception:
            st.error(
                "Could not synchronize Gmail."
            )
            logger.exception(
                "Could not synchronize Gmail."
            )

else:
    st.info(
        "Connect Gmail above to enable manual sync."
    )


# =========================================================
# MANUAL JOB SOURCE
# =========================================================

st.divider()
st.subheader("Add a job manually")

st.caption(
    "Paste a job you found somewhere else and "
    "JobHunter will include it in your opportunities."
)

with st.form(
    "manual_job_form",
    clear_on_submit=True,
):
    manual_title = st.text_input(
        "Job title *"
    )

    manual_company = st.text_input(
        "Company *"
    )

    manual_location = st.text_input(
        "Location *"
    )

    manual_description = st.text_area(
        "Job description *",
        height=250,
        placeholder=(
            "Paste the complete job description here."
        ),
    )

    manual_url = st.text_input(
        "Job URL *",
        placeholder="https://...",
    )

    manual_submit = st.form_submit_button(
        "Add job",
        type="primary",
        use_container_width=True,
    )


if manual_submit:
    title = manual_title.strip()
    company = manual_company.strip()
    location = manual_location.strip()
    description = manual_description.strip()
    url = manual_url.strip()

    missing_fields = []

    if not title:
        missing_fields.append(
            "Job title"
        )

    if not company:
        missing_fields.append(
            "Company"
        )

    if not location:
        missing_fields.append(
            "Location"
        )

    if not description:
        missing_fields.append(
            "Job description"
        )

    if not url:
        missing_fields.append(
            "Job URL"
        )

    if missing_fields:
        st.error(
            "Complete all required fields: "
            + ", ".join(missing_fields)
            + "."
        )

    else:
        parsed_url = urlparse(url)

        valid_url = (
            parsed_url.scheme
            in {
                "http",
                "https",
            }
            and bool(parsed_url.netloc)
        )

        if not valid_url:
            st.error(
                "Enter a valid job URL starting "
                "with http:// or https://."
            )

        else:
            normalized_url = (
                url.strip().lower()
            )

            job_id = (
                "manual_"
                + hashlib.sha256(
                    normalized_url.encode(
                        "utf-8"
                    )
                ).hexdigest()[:24]
            )

            raw_text = (
                f"Title: {title}\n"
                f"Company: {company}\n"
                f"Location: {location}\n"
                f"URL: {url}\n\n"
                f"{description}"
            )

            manual_job = Job(
                id=job_id,
                raw_text=raw_text,
                url=url,
                title=title,
                company=company,
                location=location,
                description=description,
            )

            upsert_raw_job(
                manual_job
            )

            job_source_repository.add_source(
                job_id=job_id,
                user_id=selected_user.id,
                source_type="manual",
            )

            st.success(
                "Job added. It will be considered "
                "in the next opportunity scan."
            )

            st.rerun()

