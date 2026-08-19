import logging
import streamlit as st
from openai import RateLimitError

from services.career_development_manager import (
    get_or_generate_career_development,
)
logger = logging.getLogger(__name__)

from services.session_auth import (
    require_login,
    render_logout_button,
)


st.set_page_config(
    page_title="Improvement",
    page_icon="📈",
    layout="wide",
)

st.title("Career Improvement")

current_user = require_login()
render_logout_button()

candidate_id = current_user.candidate_id

if not candidate_id:
    st.error(
        "Your account does not have a professional profile."
    )
    st.stop()


def render_list(
    title: str,
    items: list[str],
) -> None:
    st.subheader(title)

    if not items:
        st.caption(
            "Not enough information yet."
        )
        return

    for item in items:
        st.write(f"- {item}")


try:
    with st.spinner(
        "Analyzing your career development priorities..."
    ):
        recommendation = (
            get_or_generate_career_development(
                candidate_id
            )
        )

except RateLimitError as error:
    logger.exception(
        "OpenAI quota unavailable for career improvement."
    )

    error_code = getattr(
        getattr(error, "body", None),
        "code",
        None,
    )

    st.warning(
        "Career Improvement could not be generated because "
        "the AI service currently has no available API credit."
    )

    st.caption(
        "Your career data is safe. No recommendation was saved, "
        "and you can try again after API credit is available."
    )

    st.stop()

except Exception:
    logger.exception(
        "Could not generate career improvement analysis."
    )

    st.error(
        "Could not generate your career improvement analysis. "
        "Please try again later."
    )

    st.stop()


current_position = recommendation.get(
    "current_position",
    "",
)

if current_position:
    st.subheader("Where you are now")
    st.write(current_position)


confidence = recommendation.get(
    "data_confidence",
    "low",
)

st.caption(
    f"Analysis confidence: {confidence.title()}"
)


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

st.divider()
st.header("Development Priorities")

if not priorities:
    st.info(
        "Not enough data to identify clear "
        "development priorities yet."
    )

for index, priority in enumerate(
    priorities,
    start=1,
):
    area = priority.get(
        "area",
        "Development area",
    )

    level = priority.get(
        "priority",
        "medium",
    )

    with st.expander(
        f"{index}. {area} [{level.upper()}]",
        expanded=index == 1,
    ):
        why = priority.get(
            "why_it_matters",
            "",
        )

        if why:
            st.markdown(
                "**Why it matters**"
            )
            st.write(why)

        evidence = priority.get(
            "evidence",
            [],
        )

        if evidence:
            st.markdown(
                "**Evidence behind this priority**"
            )

            for item in evidence:
                st.write(
                    f"- {item}"
                )

        action = priority.get(
            "suggested_action",
            "",
        )

        if action:
            st.markdown(
                "**Next action**"
            )
            st.write(action)


st.divider()

render_list(
    "Strengths to leverage",
    recommendation.get(
        "strengths_to_leverage",
        [],
    ),
)

render_list(
    "Patterns in opportunities",
    recommendation.get(
        "market_patterns",
        [],
    ),
)

render_list(
    "Patterns in applications",
    recommendation.get(
        "application_patterns",
        [],
    ),
)

render_list(
    "Next best moves",
    recommendation.get(
        "next_best_moves",
        [],
    ),
)
