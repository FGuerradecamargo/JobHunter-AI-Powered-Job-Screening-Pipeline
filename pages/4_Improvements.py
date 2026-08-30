import logging

import streamlit as st
from openai import RateLimitError

from services.career_development_manager import (
    get_or_generate_career_development,
)
from services.session_auth import (
    require_login,
    render_logout_button,
)


logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="Career Development",
    page_icon="📈",
    layout="wide",
)

st.caption("CAREER GROWTH")
st.title("Career Development")

st.write(
    "A focused view of where you are, what the market is "
    "showing and what may be worth developing next."
)

current_user = require_login()
render_logout_button()

candidate_id = current_user.candidate_id

if not candidate_id:
    st.error(
        "Your account does not have a professional profile."
    )
    st.stop()


def clean_items(items) -> list[str]:
    return [
        str(item).strip()
        for item in (items or [])
        if str(item).strip()
    ]


try:
    with st.spinner(
        "Looking at your career direction and recent market signals..."
    ):
        recommendation = (
            get_or_generate_career_development(
                candidate_id
            )
        )

except RateLimitError:
    logger.exception(
        "OpenAI quota unavailable for career development."
    )

    st.warning(
        "I couldn't update your career development view "
        "right now because the AI service is temporarily unavailable."
    )

    st.stop()

except Exception:
    logger.exception(
        "Could not generate career development analysis."
    )

    st.error(
        "I couldn't update your career development view "
        "right now. Please try again later."
    )

    st.stop()


# =========================================================
# WHERE YOU ARE NOW
# =========================================================

current_position = str(
    recommendation.get(
        "current_position",
        "",
    )
).strip()

strengths = clean_items(
    recommendation.get(
        "strengths_to_leverage",
        [],
    )
)

market_patterns = clean_items(
    recommendation.get(
        "market_patterns",
        [],
    )
)

if current_position:
    st.write(current_position)

with st.expander(
    "Where you are now",
    expanded=False,
):
    if strengths:
        st.markdown("**Strengths to leverage**")

        for item in strengths:
            st.write(item)

    if market_patterns:
        st.markdown("**Market patterns**")

        for item in market_patterns:
            st.write(item)


# =========================================================
# WHAT TO FOCUS ON
# =========================================================

priorities = [
    priority
    for priority in recommendation.get(
        "top_development_priorities",
        [],
    )
    if (
        priority.get("area")
        and priority.get("why_it_matters")
        and priority.get("suggested_action")
    )
]

st.subheader("What to focus on next")

if not priorities:
    st.info(
        "There isn't enough consistent market evidence yet "
        "to recommend a clear development priority."
    )

for priority in priorities:
    area = str(
        priority.get(
            "area",
            "",
        )
    ).strip()

    why = str(
        priority.get(
            "why_it_matters",
            "",
        )
    ).strip()

    action = str(
        priority.get(
            "suggested_action",
            "",
        )
    ).strip()

    with st.expander(
        area or "Development priority",
        expanded=False,
    ):
        if why:
            st.write(why)

        if action:
            st.markdown(
                f"**Suggested action:** {action}"
            )


# =========================================================
# APPLICATION SIGNAL
# =========================================================

application_patterns = clean_items(
    recommendation.get(
        "application_patterns",
        [],
    )
)

if application_patterns:
    with st.expander(
        "Application signals",
        expanded=False,
    ):
        for item in application_patterns:
            st.write(item)


# =========================================================
# NEXT MOVES
# =========================================================

next_moves = clean_items(
    recommendation.get(
        "next_best_moves",
        [],
    )
)

if next_moves:
    with st.expander(
        "Your next moves",
        expanded=False,
    ):
        for index, move in enumerate(
            next_moves,
            start=1,
        ):
            st.markdown(
                f"**{index}.** {move}"
            )


# =========================================================
# QUIET CONFIDENCE NOTE
# =========================================================

confidence = str(
    recommendation.get(
        "data_confidence",
        "low",
    )
).strip().lower()

confidence_messages = {
    "high": (
        "This guidance is based on a strong recurring pattern "
        "in your market and career data."
    ),
    "medium": (
        "There is a useful pattern forming here, although it may "
        "change as we collect more market and application data."
    ),
    "low": (
        "This is still an early reading and should become more "
        "useful as more market and application data comes in."
    ),
}

confidence_label = {
    "high": "High confidence",
    "medium": "Medium confidence",
    "low": "Early signal",
}.get(
    confidence,
    "Early signal",
)

st.caption(
    confidence_label
    + " · "
    + confidence_messages.get(
        confidence,
        confidence_messages["low"],
    )
)
