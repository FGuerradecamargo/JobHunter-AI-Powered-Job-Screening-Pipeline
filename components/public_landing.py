"""Public presentation only; authentication and identity live elsewhere."""

import streamlit as st

from components.workpilot_ui import apply_theme


def render_public_theme() -> None:
    apply_theme()


def _open_login(intent: str) -> None:
    # A display preference, never an authorization decision.
    st.session_state["public_auth_intent"] = intent
    st.switch_page("pages/0_Login.py")


def render_auth_intro() -> None:
    st.html(
        '''
        <section class="wp-auth-intro">
          <p class="wp-wordmark">WorkPilot</p>
          <p class="wp-auth-kicker">CAREER, WITH LESS NOISE</p>
          <h1>Welcome to WorkPilot.</h1>
          <p class="wp-auth-copy">
            WorkPilot keeps your profile, opportunities and next steps connected
            so you can focus on the decisions that matter.
          </p>
          <div class="wp-seasonal-mark" aria-hidden="true">✦</div>
        </section>
        '''
    )


def _render_product_preview() -> None:
    st.html(
        '''
        <section class="wp-product-preview" aria-label="Illustrative WorkPilot job categories">
          <div class="wp-preview-topline">
            <span>YOUR OPPORTUNITIES</span>
            <span class="wp-preview-dot">●</span>
          </div>
          <article class="wp-preview-card wp-preview-card-best">
            <div>
              <span class="wp-preview-label">BEST MATCH</span>
              <h3>Product Operations Specialist</h3>
              <p>Strong evidence fit · Direction aligned</p>
            </div>
            <span class="wp-preview-score">92%</span>
          </article>
          <article class="wp-preview-card wp-preview-card-worth">
            <div>
              <span class="wp-preview-label">WORTH A TRY</span>
              <h3>Customer Operations Analyst</h3>
              <p>Relevant strengths · Some stretch</p>
            </div>
            <span class="wp-preview-score">78%</span>
          </article>
          <article class="wp-preview-card wp-preview-card-strong">
            <div>
              <span class="wp-preview-label">YOU'RE STRONG, BUT</span>
              <h3>Support Operations Lead</h3>
              <p>You fit well · Direction is weaker</p>
            </div>
            <span class="wp-preview-score">71%</span>
          </article>
          <p class="wp-preview-footnote">Illustrative product preview — not live market statistics.</p>
        </section>
        '''
    )


def render_public_landing() -> None:
    render_public_theme()

    with st.container(key="wp-public-home"):
        brand, spacer, how_it_works, login, start = st.columns(
            [1.6, 3.4, 1.25, 1.0, 1.15],
            gap="small",
            vertical_alignment="center",
        )

        with brand:
            st.html('<div class="wp-public-wordmark">WorkPilot</div>')
        with spacer:
            st.empty()
        with how_it_works:
            st.html('<a class="wp-public-nav-link" href="#how-it-works">How it works</a>')
        with login:
            if st.button(
                "Log in",
                key="public_existing_account",
                use_container_width=True,
            ):
                _open_login("login")
        with start:
            if st.button(
                "Get started",
                type="primary",
                key="public_start_career",
                use_container_width=True,
            ):
                _open_login("signup")

        st.html('<div class="wp-public-nav-rule"></div>')

        hero_copy, hero_preview = st.columns(
            [1.02, 0.98],
            gap="large",
            vertical_alignment="center",
        )

        with hero_copy:
            st.html(
                '''
                <section class="wp-public-hero-copy">
                  <p class="wp-public-kicker">YOUR CAREER, WITH LESS NOISE</p>
                  <h1>Find jobs that make sense for you.</h1>
                  <p class="wp-public-lede">
                    WorkPilot learns your professional profile, understands what employers
                    are looking for, and helps you decide where your time is actually worth investing.
                  </p>
                  <div class="wp-public-proofline">
                    <span>Understand the fit.</span>
                    <span>See the trade-offs.</span>
                    <span>You decide.</span>
                  </div>
                </section>
                '''
            )
            cta, secondary = st.columns([0.9, 1.6], vertical_alignment="center")
            with cta:
                if st.button(
                    "Get started",
                    type="primary",
                    key="public_hero_start",
                    use_container_width=True,
                ):
                    _open_login("signup")
            with secondary:
                st.html('<p class="wp-public-login-note">Already have an account? Use <strong>Log in</strong> above.</p>')

        with hero_preview:
            _render_product_preview()

        st.html(
            '''
            <section id="how-it-works" class="wp-public-section wp-how-it-works">
              <p class="wp-public-section-kicker">HOW IT WORKS</p>
              <h2>Less searching. More understanding.</h2>
              <div class="wp-how-grid">
                <article>
                  <span class="wp-step-number">01</span>
                  <h3>WorkPilot gets to know you</h3>
                  <p>Your experience, direction, priorities and constraints stay connected in one professional profile.</p>
                </article>
                <article>
                  <span class="wp-step-number">02</span>
                  <h3>WorkPilot understands the opportunity</h3>
                  <p>Each role is interpreted against what the employer needs and what matters to you now.</p>
                </article>
                <article>
                  <span class="wp-step-number">03</span>
                  <h3>You decide</h3>
                  <p>See the evidence, gaps and trade-offs before you choose where to invest your time.</p>
                </article>
              </div>
            </section>
            '''
        )

        st.html(
            '''
            <section class="wp-public-section wp-not-job-board">
              <div>
                <p class="wp-public-section-kicker">A DIFFERENT KIND OF SEARCH</p>
                <h2>Not another job board.</h2>
                <p class="wp-not-job-board-lede">A vacancy is only useful when the relationship makes sense.</p>
              </div>
              <p>
                Traditional job boards mainly help you find openings. WorkPilot looks at the
                relationship between your evidence, the opportunity and the market so you can
                understand what deserves your attention — without making the decision for you.
              </p>
            </section>
            '''
        )

        closing_copy, closing_action = st.columns(
            [2.2, 0.8],
            gap="large",
            vertical_alignment="center",
        )
        with closing_copy:
            st.html(
                '''
                <section class="wp-public-closing-copy">
                  <p class="wp-public-section-kicker">READY WHEN YOU ARE</p>
                  <h2>Ready to build your profile?</h2>
                  <p>Start with a short conversation about the work you have actually done.</p>
                </section>
                '''
            )
        with closing_action:
            if st.button(
                "Get started",
                type="primary",
                key="public_closing_start",
                use_container_width=True,
            ):
                _open_login("signup")
