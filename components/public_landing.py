"""Static public surfaces. Authentication and account data live elsewhere."""
from base64 import b64encode
from pathlib import Path

import streamlit as st


ASSETS = Path(__file__).parent


def render_public_theme() -> None:
    css = (ASSETS / "public_seasonal.css").read_text(encoding="utf-8")
    st.html('<style>' + css + '</style><span class="wp-seasonal" aria-hidden="true"></span>')


def _ornament() -> str:
    asset = b64encode((ASSETS / "assets" / "autumn-web.svg").read_bytes()).decode("ascii")
    return '<img class="wp-web" alt="" aria-hidden="true" src="data:image/svg+xml;base64,' + asset + '">'


def _open_login(intent: str) -> None:
    # Presentation preference only; never used to authorize or resolve identity.
    st.session_state["public_auth_intent"] = intent
    st.switch_page("pages/0_Login.py")


def render_auth_intro() -> None:
    st.html('''<section class="wp-auth-intro">
      <p class="wp-wordmark">WorkPilot<span>.</span></p>
      <p class="wp-kicker">YOUR NEXT CHAPTER</p>
      <h1>Welcome to <br>WorkPilot.</h1>
      <p>A little less noise.<br>A little more clarity.</p>
      <div class="wp-auth-detail" aria-hidden="true">''' + _ornament() + '''</div>
      <p class="wp-auth-trust">Your career. Your decisions.</p>
    </section>''')


def render_public_landing() -> None:
    render_public_theme()
    with st.container(key="wp-public-home"):
        with st.container(key="wp-public-nav"):
            brand, account = st.columns([1, 1])
            with brand:
                st.html('<p class="wp-wordmark">WorkPilot<span>.</span></p>')
            with account:
                if st.button("I already have an account", key="public_existing_account"):
                    _open_login("login")

        with st.container(key="wp-home-hero"):
            copy, concept = st.columns([1.15, 1], gap="large")
            with copy:
                st.html('''<section class="wp-hero-copy">
                  <p class="wp-kicker">WORKPILOT / AUTUMN EDITION</p>
                  <h1>Finding a job<br>shouldn't become<br><em>a second job.</em></h1>
                  <p>There are hundreds of jobs out there.<br>Most of them don't deserve your attention.</p>
                  <p class="wp-muted">WorkPilot learns how you work, keeps an eye on the market, and shows you what's worth a closer look.</p>
                </section>''')
                if st.button("Start with my career", type="primary", key="public_start_career"):
                    _open_login("signup")
            with concept:
                st.html('''<figure class="wp-funnel" aria-label="Illustrative market filtering example">'''
                    + _ornament() + '''
                  <figcaption>ILLUSTRATIVE EXAMPLE <span>MORE &rarr; LESS &rarr; RELEVANT</span></figcaption>
                  <div class="wp-stage wp-stage-one"><div><span>MARKET NOISE</span><strong>385</strong></div><p>opportunities</p></div>
                  <p class="wp-connector">&darr; WorkPilot filters</p>
                  <div class="wp-stage wp-stage-two"><strong>40</strong><p>recently seen</p></div>
                  <p class="wp-connector">&darr; understands context</p>
                  <div class="wp-stage wp-stage-three"><strong>10</strong><p>worth analysing</p></div>
                  <p class="wp-connector">&darr; prioritises attention</p>
                  <div class="wp-stage wp-stage-four"><strong>3</strong><p>worth a closer look</p></div>
                  <p class="wp-disclaimer">Illustrative numbers, not live market statistics or promised results.</p>
                </figure>''')

        st.html('''<div class="wp-public-sections">
          <section class="wp-band wp-contrast">
            <div><p class="wp-kicker">MORE JOBS &ne; BETTER SEARCH</p><p class="wp-muted">Job boards help you find jobs.</p></div>
            <h2>WorkPilot helps you decide<br><em>which ones deserve your time.</em></h2>
          </section>
          <section class="wp-band wp-steps" aria-label="Understand, filter, decide">
            <article><span class="wp-step-number">01</span><p class="wp-kicker">UNDERSTAND</p><h3>Tell WorkPilot how<br>you actually work.</h3><p>Not just your job title.<br>What you do. What you solve.<br>What people rely on you for.</p></article>
            <article><span class="wp-step-number">02</span><p class="wp-kicker">FILTER</p><h3>The market, through<br>your context.</h3><p>WorkPilot compares the market with the professional you actually are.</p><p>Not just keywords against keywords.</p></article>
            <article><span class="wp-step-number">03</span><p class="wp-kicker">DECIDE</p><h3>See what fits.<br>See what doesn't. See why.</h3><p>You make the career decision.</p></article>
          </section>
          <section class="wp-band wp-product">
            <div class="wp-section-intro"><p class="wp-kicker">A CLOSER LOOK</p><h2>Not just a match.<br><em>A reason to pay attention.</em></h2><p class="wp-muted">Illustrative opportunity. Not a live vacancy or a personal assessment.</p></div>
            <article class="wp-demo" aria-label="Illustrative opportunity">
              <div class="wp-preview-bar"><span>WORKPILOT / OPPORTUNITIES</span><span>ILLUSTRATIVE PREVIEW</span></div>
              <header><div><h3>TECHNICAL SUPPORT SPECIALIST</h3><p>Enterprise SaaS</p></div><span class="wp-match">Potential match</span></header>
              <div class="wp-evidence">
                <div><h4>WHY IT'S WORTH A LOOK</h4><ul><li>Strong overlap with customer problem solving</li><li>Experience working across support systems</li><li>Relevant stakeholder communication</li></ul></div>
                <div class="wp-watch"><h4>WATCH OUT FOR</h4><ul><li>Role asks for deeper API troubleshooting</li><li>Some ownership expectations are above your current evidence</li></ul></div>
              </div>
              <footer><span class="wp-kicker">WORKPILOT'S VIEW</span><h3>Worth a closer look.</h3><p>You have enough overlap to compete,<br>but there are meaningful gaps to consider.</p></footer>
            </article>
          </section>
          <section class="wp-band wp-career">
            <div><p class="wp-kicker">YOUR CV ISN'T YOUR WHOLE CAREER.</p><h2>More than the document.<br><em>The professional behind it.</em></h2><p>A CV is a document you wrote for a purpose.</p><p class="wp-muted">Your career is everything you've actually done, solved, learned and been trusted with.</p><p>WorkPilot starts there.</p></div>
            <div class="wp-context"><blockquote>&ldquo;I work in customer support&rdquo;</blockquote><div class="wp-arrow" aria-hidden="true">&darr;</div><ul><li>customers</li><li>systems</li><li>escalation</li><li>problem solving</li><li>communication</li><li>decisions</li><li>evidence</li><li>outcomes</li></ul><div class="wp-arrow" aria-hidden="true">&darr;</div><strong>YOUR PROFESSIONAL CONTEXT</strong></div>
          </section>
          <section class="wp-band wp-closing"><p class="wp-kicker">NO TRICKS. JUST BETTER JOB DECISIONS.</p><h2>You take care of your career.<br><em>WorkPilot takes care of the work around it.</em></h2><p class="wp-muted">No auto-apply. No career decisions made for you.</p></section>
        </div>''')
        with st.container(key="wp-closing-action"):
            if st.button("Start with my career", type="primary", key="public_closing_start"):
                _open_login("signup")
