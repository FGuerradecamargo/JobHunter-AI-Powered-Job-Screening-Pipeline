import streamlit as st


# =========================================================
# WORKPILOT — PUBLIC HOME
# =========================================================

st.markdown(
    """
    <style>
    :root {
        --wp-navy: #073E49;
        --wp-teal: #075665;
        --wp-bg: #F8FAF9;
        --wp-card: #FFFFFF;
        --wp-text: #18363D;
        --wp-muted: #65777C;
        --wp-border: #DFE7E7;
        --wp-soft: #E9F3F3;
    }

    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    section.main,
    main {
        background: var(--wp-bg) !important;
        color: var(--wp-text) !important;
    }

    [data-testid="stHeader"] {
        background: rgba(248, 250, 249, 0.94) !important;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2.4rem;
        padding-bottom: 5rem;
    }

    /* -----------------------------------------------------
       HERO
       ----------------------------------------------------- */

    .wp-home-eyebrow {
        color: var(--wp-teal);
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }

    .wp-home-title {
        color: var(--wp-text);
        font-size: clamp(3rem, 6vw, 5.3rem);
        line-height: 0.98;
        max-width: 760px;
        font-weight: 800;
        letter-spacing: -0.055em;
        margin-bottom: 1.5rem;
    }

    .wp-home-subtitle {
        color: var(--wp-muted);
        font-size: 1.18rem;
        line-height: 1.65;
        max-width: 720px;
        margin-bottom: 1.5rem;
    }

    .wp-home-note {
        color: #7A8A8E;
        font-size: 0.88rem;
        line-height: 1.5;
        margin-top: 0.65rem;
    }

    /* -----------------------------------------------------
       PRODUCT PREVIEW
       ----------------------------------------------------- */

    .wp-preview {
        background: #FFFFFF;
        border: 1px solid var(--wp-border);
        border-radius: 18px;
        padding: 1.5rem;
        box-shadow:
            0 20px 50px rgba(7, 62, 73, 0.08);
        margin-top: 0.5rem;
    }

    .wp-preview-label {
        color: #789095;
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 0.09em;
        margin-bottom: 1rem;
    }

    .wp-preview-profile {
        display: flex;
        align-items: center;
        gap: 0.9rem;
        margin-bottom: 1.4rem;
    }

    .wp-preview-avatar {
        width: 46px;
        height: 46px;
        border-radius: 50%;
        background: #DDEEEF;
        color: var(--wp-teal);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
    }

    .wp-preview-name {
        color: var(--wp-text);
        font-weight: 750;
        font-size: 1rem;
    }

    .wp-preview-role {
        color: var(--wp-muted);
        font-size: 0.82rem;
        margin-top: 0.15rem;
    }

    .wp-match-card {
        background: #F8FBFA;
        border: 1px solid #E3EBEA;
        border-radius: 13px;
        padding: 1rem 1.05rem;
        margin-bottom: 0.75rem;
    }

    .wp-match-top {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
    }

    .wp-match-title {
        color: var(--wp-text);
        font-size: 0.93rem;
        font-weight: 700;
    }

    .wp-match-company {
        color: var(--wp-muted);
        font-size: 0.78rem;
        margin-top: 0.15rem;
    }

    .wp-match-score {
        background: #DFF0EC;
        color: #08705D;
        font-size: 0.75rem;
        font-weight: 800;
        padding: 0.25rem 0.55rem;
        border-radius: 99px;
        white-space: nowrap;
    }

    /* -----------------------------------------------------
       SECTIONS
       ----------------------------------------------------- */

    .wp-section-kicker {
        color: var(--wp-teal);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        margin-top: 4rem;
        margin-bottom: 0.75rem;
    }

    .wp-section-title {
        color: var(--wp-text);
        font-size: 2.35rem;
        line-height: 1.12;
        font-weight: 800;
        letter-spacing: -0.035em;
        max-width: 760px;
        margin-bottom: 0.8rem;
    }

    .wp-section-copy {
        color: var(--wp-muted);
        font-size: 1.02rem;
        line-height: 1.65;
        max-width: 750px;
        margin-bottom: 1.8rem;
    }

    /* -----------------------------------------------------
       FEATURE CARDS
       ----------------------------------------------------- */

    .wp-feature-card {
        background: var(--wp-card);
        border: 1px solid var(--wp-border);
        border-radius: 15px;
        padding: 1.3rem 1.25rem;
        min-height: 175px;
        box-shadow:
            0 3px 14px rgba(7, 62, 73, 0.035);
        margin-bottom: 1rem;
    }

    .wp-feature-icon {
        width: 38px;
        height: 38px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--wp-soft);
        border-radius: 10px;
        margin-bottom: 1rem;
        font-size: 1rem;
    }

    .wp-feature-title {
        color: var(--wp-text);
        font-weight: 750;
        font-size: 1rem;
        margin-bottom: 0.45rem;
    }

    .wp-feature-copy {
        color: var(--wp-muted);
        font-size: 0.88rem;
        line-height: 1.55;
    }

    /* -----------------------------------------------------
       CAREER CYCLE
       ----------------------------------------------------- */

    .wp-cycle-card {
        background: var(--wp-card);
        border: 1px solid var(--wp-border);
        border-radius: 15px;
        padding: 1.25rem;
        min-height: 190px;
        margin-bottom: 1rem;
    }

    .wp-cycle-number {
        color: var(--wp-teal);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 1.2rem;
    }

    .wp-cycle-title {
        color: var(--wp-text);
        font-size: 1rem;
        font-weight: 750;
        margin-bottom: 0.55rem;
    }

    .wp-cycle-copy {
        color: var(--wp-muted);
        font-size: 0.87rem;
        line-height: 1.55;
    }

    /* -----------------------------------------------------
       FINAL CTA
       ----------------------------------------------------- */

    .wp-final {
        background: #073E49;
        border-radius: 20px;
        padding: 3.2rem 2rem 2.6rem 2rem;
        text-align: center;
        margin-top: 4rem;
        margin-bottom: 1.2rem;
    }

    .wp-final-title {
        color: #FFFFFF;
        font-size: 2.35rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin-bottom: 0.7rem;
    }

    .wp-final-copy {
        color: #C8DADA;
        font-size: 1rem;
        line-height: 1.6;
        max-width: 620px;
        margin: 0 auto;
    }

    /* -----------------------------------------------------
       BUTTONS
       ----------------------------------------------------- */

    .stButton > button {
        border-radius: 9px !important;
        min-height: 2.85rem !important;
        font-weight: 650 !important;
    }

    .stButton > button[kind="primary"] {
        background: #075665 !important;
        border-color: #075665 !important;
        color: #FFFFFF !important;
    }

    .stButton > button[kind="primary"] * {
        color: #FFFFFF !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: #064954 !important;
        border-color: #064954 !important;
    }

    .stButton > button:not([kind="primary"]) {
        background: #FFFFFF !important;
        border: 1px solid #B8C8CB !important;
        color: #123F4A !important;
    }

    .stButton > button:not([kind="primary"]) * {
        color: #123F4A !important;
    }

    .stButton > button:not([kind="primary"]):hover {
        background: #EEF5F5 !important;
        border-color: #075665 !important;
        color: #075665 !important;
    }

    .stButton > button:not([kind="primary"]):hover * {
        color: #075665 !important;
    }

    @media (max-width: 800px) {
        .block-container {
            padding-top: 1.2rem;
        }

        .wp-home-title {
            font-size: 3rem;
        }

        .wp-section-title {
            font-size: 2rem;
        }

        .wp-preview {
            margin-top: 2rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HERO
# =========================================================

hero_left, hero_right = st.columns(
    [1.45, 0.8],
    gap="large",
)

with hero_left:
    st.html(
        """
        <div class="wp-home-eyebrow">
            YOUR CAREER. ONE SYSTEM.
        </div>

        <div class="wp-home-title">
            Take control of your career.
        </div>

        <div class="wp-home-subtitle">
            WorkPilot helps you understand where you stand,
            find the right opportunities, build stronger
            applications and decide where to grow — without
            turning career management into another full-time job.
        </div>
        """
    )

    button_1, button_2, button_space = st.columns(
        [1.05, 1.0, 2.7]
    )

    with button_1:
        if st.button(
            "Get started",
            type="primary",
            use_container_width=True,
            key="hero_get_started",
        ):
            st.switch_page("pages/0_Login.py")

    with button_2:
        if st.button(
            "Log in",
            use_container_width=True,
            key="hero_login",
        ):
            st.switch_page("pages/0_Login.py")

    st.html(
        """
        <div class="wp-home-note">
            Spend less time managing your career.
            Get your time back.
        </div>
        """
    )


with hero_right:
    st.html(
        """
        <div class="wp-preview">
            <div class="wp-preview-label">
                YOUR CAREER TODAY
            </div>

            <div class="wp-preview-profile">
                <div class="wp-preview-avatar">WP</div>

                <div>
                    <div class="wp-preview-name">
                        Career Profile
                    </div>

                    <div class="wp-preview-role">
                        Built from your real experience + direction
                    </div>
                </div>
            </div>

            <div class="wp-match-card">
                <div class="wp-match-top">
                    <div>
                        <div class="wp-match-title">
                            Senior Operations Specialist
                        </div>

                        <div class="wp-match-company">
                            Strong evidence across operations,
                            support and process improvement
                        </div>
                    </div>

                    <div class="wp-match-score">
                        BEST MATCH
                    </div>
                </div>
            </div>

            <div class="wp-match-card">
                <div class="wp-match-top">
                    <div>
                        <div class="wp-match-title">
                            Customer Experience Lead
                        </div>

                        <div class="wp-match-company">
                            Good alignment with transferable
                            leadership experience
                        </div>
                    </div>

                    <div class="wp-match-score">
                        POTENTIAL
                    </div>
                </div>
            </div>
        </div>
        """
    )


# =========================================================
# VALUE PROPOSITION
# =========================================================

st.html(
    """
    <div class="wp-section-kicker">
        EVERYTHING IN ONE PLACE
    </div>

    <div class="wp-section-title">
        Your career should not become another full-time job.
    </div>

    <div class="wp-section-copy">
        Job searching is only one piece of the problem.
        Comparing opportunities, tailoring applications,
        tracking outcomes, understanding the market and deciding
        what to improve all take time. WorkPilot brings that
        work into one continuous system.
    </div>
    """
)


features = [
    (
        "⌕",
        "Discover",
        "Surface opportunities that make sense for both "
        "your evidence and where you want to go.",
    ),
    (
        "◎",
        "Apply smarter",
        "Understand your fit and build stronger applications "
        "using your real professional evidence.",
    ),
    (
        "✓",
        "Stay organised",
        "Keep applications, interviews, rejections, offers "
        "and feedback connected.",
    ),
    (
        "↗",
        "Understand the market",
        "See what employers are actually asking for around "
        "the career you are targeting.",
    ),
    (
        "△",
        "Improve strategically",
        "Identify the experience and skill gaps that are "
        "actually worth working on.",
    ),
    (
        "◷",
        "Get your time back",
        "Reduce repetitive career admin so your attention "
        "can stay on the rest of your life.",
    ),
]


for row_start in (0, 3):
    columns = st.columns(3, gap="medium")

    for column, item in zip(
        columns,
        features[row_start:row_start + 3],
    ):
        icon, title, copy = item

        with column:
            st.html(
                f"""
                <div class="wp-feature-card">
                    <div class="wp-feature-icon">
                        {icon}
                    </div>

                    <div class="wp-feature-title">
                        {title}
                    </div>

                    <div class="wp-feature-copy">
                        {copy}
                    </div>
                </div>
                """
            )


# =========================================================
# CAREER CYCLE
# =========================================================

st.html(
    """
    <div class="wp-section-kicker">
        NOT JUST A JOB SEARCH
    </div>

    <div class="wp-section-title">
        One continuous career cycle.
    </div>

    <div class="wp-section-copy">
        WorkPilot treats every opportunity, application and
        outcome as information. Your system becomes more useful
        as your career evolves.
    </div>
    """
)


cycle = [
    (
        "01",
        "Build your career profile",
        "Turn your experience into structured evidence "
        "without letting your past dictate your direction.",
    ),
    (
        "02",
        "Choose where you want to go",
        "Define the work, priorities and direction that matter "
        "to you now.",
    ),
    (
        "03",
        "Act on the right opportunities",
        "Review matches, tailor applications and keep the "
        "whole process organised.",
    ),
    (
        "04",
        "Learn from reality",
        "Use market demand and actual application outcomes "
        "to decide what to do next.",
    ),
]


cycle_columns = st.columns(4, gap="medium")

for column, item in zip(
    cycle_columns,
    cycle,
):
    number, title, copy = item

    with column:
        st.html(
            f"""
            <div class="wp-cycle-card">
                <div class="wp-cycle-number">
                    {number}
                </div>

                <div class="wp-cycle-title">
                    {title}
                </div>

                <div class="wp-cycle-copy">
                    {copy}
                </div>
            </div>
            """
        )


# =========================================================
# FINAL CTA
# =========================================================

st.html(
    """
    <div class="wp-final">
        <div class="wp-final-title">
            Spend less time managing your career.
        </div>

        <div class="wp-final-copy">
            Build one career system that helps you understand
            where you are, decide where you are going and act
            with better information.
        </div>
    </div>
    """
)


cta_left, cta_center, cta_right = st.columns(
    [2.1, 1.45, 2.1]
)

with cta_center:
    if st.button(
        "Start with WorkPilot →",
        type="primary",
        use_container_width=True,
        key="final_get_started",
    ):
        st.switch_page("pages/0_Login.py")
