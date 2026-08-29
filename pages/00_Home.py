import streamlit as st


st.markdown(
    """
    <style>
    html, body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    section.main,
    main {
        background-color: #F7F9F8 !important;
        color: #123F4A !important;
    }

    [data-testid="stHeader"] {
        background-color: #F7F9F8 !important;
    }

    [data-testid="stSidebar"],
    [data-testid="stSidebarContent"] {
        background-color: #F5F7F8 !important;
    }

    div[data-testid="stMarkdownContainer"],
    div[data-testid="stMarkdownContainer"] * {
        color: #123F4A !important;
    }

    .stCaption,
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] * {
        color: #5C6F75 !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #F7F9F8 !important;
    }
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    .jh-eyebrow {
        color: #5C6F75;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        opacity: 0.6;
        margin-top: 2.5rem;
        margin-bottom: 0.8rem;
    }

    .jh-title {
        color: #123F4A;
        font-size: 3.8rem;
        line-height: 1.02;
        font-weight: 800;
        letter-spacing: -0.045em;
        margin-bottom: 1.2rem;
    }

    .jh-subtitle {
        color: #5C6F75;
        font-size: 1.25rem;
        line-height: 1.55;
        opacity: 0.75;
        max-width: 760px;
        margin-bottom: 1.5rem;
    }

    .jh-section-title {
        color: #123F4A;
        font-size: 2rem;
        line-height: 1.15;
        font-weight: 750;
        letter-spacing: -0.025em;
        margin-top: 3.5rem;
        margin-bottom: 0.7rem;
    }

    .jh-section-copy {
        color: #5C6F75;
        font-size: 1.05rem;
        line-height: 1.55;
        opacity: 0.72;
        max-width: 760px;
        margin-bottom: 1.6rem;
    }

    .jh-final {
        text-align: center;
        margin-top: 4rem;
    }

    .jh-final-title {
        color: #123F4A;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.7rem;
    }

    .jh-final-copy {
        color: #5C6F75;
        font-size: 1.08rem;
        line-height: 1.5;
        opacity: 0.72;
        max-width: 650px;
        margin: 0 auto 1.5rem auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# HERO
# ---------------------------------------------------------

st.markdown(
    '<div class="jh-eyebrow">Your career. One system.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="jh-title">Take control of your career.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="jh-subtitle">'
    'JobHunter helps you find the right opportunities, '
    'understand the market, tailor your applications, '
    'track your progress and know where to grow — '
    'while giving you your time back.'
    '</div>',
    unsafe_allow_html=True,
)


hero_col1, hero_col2, hero_space = st.columns(
    [1.15, 1.15, 3.7]
)

with hero_col1:
    if st.button(
        "Get started",
        type="primary",
        use_container_width=True,
    ):
        st.switch_page("pages/0_Login.py")

with hero_col2:
    if st.button(
        "Log in",
        use_container_width=True,
    ):
        st.switch_page("pages/0_Login.py")


st.caption(
    "Spend less time managing your career "
    "and more time focusing on everything else."
)


# ---------------------------------------------------------
# VALUE PROPOSITION
# ---------------------------------------------------------

st.markdown(
    '<div class="jh-section-title">'
    'Your career should not become another full-time job.'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="jh-section-copy">'
    'Searching across multiple platforms, comparing jobs, '
    'tailoring CVs, tracking applications, researching the '
    'market and deciding what to learn next takes time. '
    'JobHunter brings that work together.'
    '</div>',
    unsafe_allow_html=True,
)


row1 = st.columns(3)

cards_1 = [
    (
        "🔎 Discover",
        "Continuously surface opportunities that actually "
        "make sense for your profile and career direction.",
    ),
    (
        "🎯 Apply smarter",
        "Understand your fit for each role and build a "
        "tailored application using your real professional evidence.",
    ),
    (
        "📋 Stay organised",
        "Keep applications, interviews, rejections, offers "
        "and feedback together in one place.",
    ),
]

for column, (title, copy) in zip(
    row1,
    cards_1,
):
    with column:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(copy)


row2 = st.columns(3)

cards_2 = [
    (
        "📊 Understand the market",
        "See what employers are actually asking for and how "
        "demand is changing around your target career.",
    ),
    (
        "📈 Improve strategically",
        "Identify which skills and experience gaps are "
        "genuinely worth working on next.",
    ),
    (
        "⏱️ Get your time back",
        "Reduce the repetitive work around managing your "
        "career so you can focus on living it.",
    ),
]

for column, (title, copy) in zip(
    row2,
    cards_2,
):
    with column:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(copy)


# ---------------------------------------------------------
# CAREER CYCLE
# ---------------------------------------------------------

st.markdown(
    '<div class="jh-section-title">'
    'One continuous career cycle.'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="jh-section-copy">'
    'JobHunter does not treat your career as a single job '
    'search. It learns from your profile, the market and '
    'the results of your applications over time.'
    '</div>',
    unsafe_allow_html=True,
)


steps = st.columns(4)

step_content = [
    (
        "01",
        "Build your career profile",
        "Your experience becomes evidence the system can "
        "use — not a direction it forces on you.",
    ),
    (
        "02",
        "Choose where you want to go",
        "Tell JobHunter what matters to you and what kind "
        "of work you want next.",
    ),
    (
        "03",
        "Act on the right opportunities",
        "Review strong matches, tailor applications and "
        "track what happens.",
    ),
    (
        "04",
        "Learn and improve",
        "Use real market demand and application outcomes "
        "to guide your next move.",
    ),
]

for column, (number, title, copy) in zip(
    steps,
    step_content,
):
    with column:
        st.markdown(f"### {number}")
        st.markdown(f"**{title}**")
        st.caption(copy)


# ---------------------------------------------------------
# FINAL CTA
# ---------------------------------------------------------

st.markdown(
    '<div class="jh-final">'
    '<div class="jh-final-title">'
    'Spend less time managing your career.'
    '</div>'
    '<div class="jh-final-copy">'
    'Put the repetitive work in one place and make better '
    'career decisions with better information.'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)


cta_left, cta_center, cta_right = st.columns(
    [2, 1.5, 2]
)

with cta_center:
    if st.button(
        "Start with JobHunter",
        type="primary",
        use_container_width=True,
        key="final_get_started",
    ):
        st.switch_page("pages/0_Login.py")


