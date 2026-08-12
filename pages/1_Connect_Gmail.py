from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

import os

from services.gmail_sync_service import (
    GmailSyncService,
)

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

from services.gmail_job_processor import (
    GmailJobProcessor,
)
from services.gmail_message_repository import (
    GmailMessageRepository,
)

from services.candidate_job_analysis_service import (
    CandidateJobAnalysisService,
)

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
gmail_message_repository = GmailMessageRepository()

gmail_job_processor = GmailJobProcessor(
    gmail_message_repository=(
        gmail_message_repository
    )
)

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
        "Sync Gmail",
        type="primary",
        use_container_width=True,
        key="sync_gmail_button",
    ):
        try:
            with st.spinner(
                "Searching Gmail for job alerts..."
            ):
                sync_result = (
                    gmail_sync_service
                    .sync_recent_job_alerts(
                        user_id=selected_user.id
                    )
                )

            st.success(
                "Gmail synchronization completed."
            )

            result_columns = st.columns(3)

            result_columns[0].metric(
                "Found in Gmail",
                sync_result.total_messages_found,
            )

            result_columns[1].metric(
                "New messages",
                sync_result.new_messages_found,
            )

            result_columns[2].metric(
                "Already registered",
                sync_result.skipped_existing,
            )

        except Exception as error:
            st.error(
                "Could not synchronize Gmail."
            )
            st.exception(error)

    st.divider()

    st.subheader(
        "Process job alerts"
    )

    st.caption(
        "Extract and analyze jobs from synchronized "
        "Gmail alerts."
    )

    processing_limit = st.number_input(
        "Messages to process",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
        key="gmail_processing_limit",
    )

    if st.button(
            "Process pending alerts",
            type="primary",
            use_container_width=True,
    ):
        if not selected_user.candidate_id:
            st.error(
                "This user is not linked to a "
                "candidate profile."
            )

        else:
            try:
                with st.spinner(
                        "Extracting jobs from alerts..."
                ):
                    processing_result = (
                        gmail_job_processor
                        .process_pending_messages(
                            user_id=selected_user.id,
                            candidate_id=(
                                selected_user.candidate_id
                            ),
                            limit=int(
                                processing_limit
                            ),
                        )
                    )

                st.success(
                    "Pending alerts processed."
                )

                first_row = st.columns(4)

                first_row[0].metric(
                    "Messages selected",
                    processing_result.messages_selected,
                )

                first_row[1].metric(
                    "Processed",
                    processing_result.messages_processed,
                )

                first_row[2].metric(
                    "Failed",
                    processing_result.messages_failed,
                )

                first_row[3].metric(
                    "Without HTML",
                    processing_result.messages_without_html,
                )

                second_row = st.columns(4)

                second_row[0].metric(
                    "Jobs found",
                    processing_result.jobs_found,
                )

                second_row[1].metric(
                    "Jobs created",
                    processing_result.jobs_created,
                )

                second_row[2].metric(
                    "Jobs updated",
                    processing_result.jobs_updated,
                )

                second_row[3].metric(
                    "Already known",
                    processing_result.jobs_unchanged,
                )

                st.metric(
                    "Candidate links created",
                    processing_result.candidate_links_created,
                )

                st.divider()

                st.info(
                    "This process may take several minutes depending on the number "
                    "of pending jobs. For around 40 jobs, it may take approximately "
                    "5–15 minutes. Keep this page open and avoid refreshing or "
                    "clicking the button again while processing."
                )

                with st.spinner(
                        "Screening jobs and analyzing qualified opportunities... "
                        "Please keep this page open."
                ):
                    analysis_service = (
                        CandidateJobAnalysisService()
                    )

                    analysis_result = (
                        analysis_service.analyze_pending(
                            candidate_id=(
                                selected_user.candidate_id
                            ),
                            limit=500,
                        )
                    )

                st.success(
                    "Candidate job analysis completed."
                )

                st.subheader(
                    "Automated screening"
                )

                analysis_first_row = st.columns(4)

                analysis_first_row[0].metric(
                    "Jobs selected",
                    analysis_result["selected"],
                )

                analysis_first_row[1].metric(
                    "Analyzed",
                    analysis_result["analyzed"],
                )

                analysis_first_row[2].metric(
                    "Rule rejected",
                    (
                            analysis_result[
                                "hard_rejected"
                            ]
                            + analysis_result[
                                "matcher_rejected"
                            ]
                    ),
                )

                analysis_first_row[3].metric(
                    "Sent to AI",
                    analysis_result[
                        "ai_analyses_created"
                    ],
                )

                analysis_second_row = st.columns(4)

                analysis_second_row[0].metric(
                    "Approved for review",
                    analysis_result[
                        "ai_approved"
                    ],
                )

                analysis_second_row[1].metric(
                    "Rejected by AI",
                    analysis_result[
                        "ai_rejected"
                    ],
                )

                analysis_second_row[2].metric(
                    "Descriptions fetched",
                    analysis_result[
                        "descriptions_fetched"
                    ],
                )

                analysis_second_row[3].metric(
                    "Analysis failures",
                    analysis_result["failed"],
                )

                if analysis_result["errors"]:
                    st.warning(
                        "Some jobs could not be analyzed."
                    )

                    for item in analysis_result[
                        "errors"
                    ]:
                        st.write(
                            f"{item['title']}: "
                            f"{item['error']}"
                        )

                st.info(
                    "Open the JobHunter dashboard to "
                    "review the approved opportunities."
                )

            except Exception as error:
                st.error(
                    "Could not process or analyze "
                    "pending job alerts."
                )

                st.exception(error)

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