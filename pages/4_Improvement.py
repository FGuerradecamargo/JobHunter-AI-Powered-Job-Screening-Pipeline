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

st.title("Career Development")

st.caption(
    "A practical look at where you are and what may be worth "
    "focusing on next."
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

st.subheader("Where you are now")

if current_position:
    st.write(current_position)

for item in strengths:
    st.write(item)

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

st.subheader("What I’d focus on next")

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

    st.markdown(
        f"#### {area}"
    )

    if why:
        st.write(why)

    if action:
        st.markdown(
            f"**What I’d do:** {action}"
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
    st.markdown("#### One more thing")

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
    st.subheader("Your next moves")

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

st.divider()

st.caption(
    confidence_messages.get(
        confidence,
        confidence_messages["low"],
    )
)
