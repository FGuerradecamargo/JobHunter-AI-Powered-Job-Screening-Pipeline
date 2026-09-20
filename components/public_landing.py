"""Static public introduction. No account data, network or authentication logic."""
from base64 import b64encode
from pathlib import Path

import streamlit as st


def render_public_landing() -> None:
    diagram = b64encode(
        (Path(__file__).parent / "assets" / "attention-example.png").read_bytes()
    ).decode("ascii")
    st.html(r"""
<style>
.stMainBlockContainer:has(.wp-public-home) {max-width:1200px !important;padding-top:5rem;}
.stMain:has(.wp-public-home) {background:#F8FAF9;}
.wp-public-home {color:#18363D;font-family:inherit;letter-spacing:0;}
.wp-public-home * {box-sizing:border-box;letter-spacing:0;}
.wp-public-home p {font-size:17px;line-height:1.65;margin:0 0 18px;}
.wp-public-home h1,.wp-public-home h2,.wp-public-home h3 {color:#18363D;word-break:normal;overflow-wrap:break-word;}
.wp-public-home h1 {font-size:26px;margin:0;padding:0;font-weight:750;}
.wp-public-home h2 {font-family:Georgia,serif;font-weight:400;font-size:38px;line-height:1.2;margin:0 0 24px;padding:0;}
.wp-public-home h3 {font-size:20px;line-height:1.4;margin:14px 0;padding:0;}
.wp-public-home .wp-eyebrow {font-size:12px;font-weight:700;color:#47686E;margin-bottom:20px;}
.wp-public-home .wp-nav {display:flex;align-items:center;justify-content:space-between;gap:20px;padding-bottom:24px;border-bottom:1px solid #DCE5E3;}
.wp-public-home a {color:#075665;text-decoration:underline;text-underline-offset:5px;}
.wp-public-home a:focus-visible {outline:3px solid #C58834;outline-offset:5px;}
.wp-public-home .wp-actions {display:flex;align-items:center;gap:22px;flex-wrap:wrap;margin-top:28px;}
.wp-public-home .wp-primary {display:inline-block;background:#075665;color:white;padding:14px 22px;border-radius:6px;font-size:16px;font-weight:650;text-decoration:none;text-align:center;}
.wp-public-home .wp-primary:hover {background:#18363D;}
.wp-public-home .wp-hero {display:grid;grid-template-columns:1.12fr 1fr;gap:48px;align-items:center;padding:32px 0;}
.wp-public-home .wp-hero h2 {font-size:48px;line-height:1.08;margin-bottom:25px;}
.wp-public-home .wp-hero p {max-width:490px;}
.wp-public-home figure {margin:0 auto;min-width:0;max-width:390px;}
.wp-public-home .wp-diagram {display:block;width:100%;height:auto;aspect-ratio:1;}
.wp-public-home figcaption {font-size:12px;color:#52686D;line-height:1.5;}
.wp-public-home .wp-band {padding:58px 0;border-top:1px solid #DCE5E3;}
.wp-public-home .wp-contrast {display:grid;grid-template-columns:1fr 1.3fr;gap:48px;}
.wp-public-home .wp-contrast p {color:#52686D;}
.wp-public-home .wp-steps {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;}
.wp-public-home .wp-step {background:white;border:1px solid #DCE5E3;border-radius:8px;padding:28px;}
.wp-public-home .wp-step .wp-number {color:#9A6225;font-size:13px;font-weight:700;}
.wp-public-home .wp-step p {font-size:16px;}
.wp-public-home .wp-demo-intro {max-width:640px;margin-bottom:28px;}
.wp-public-home .wp-demo {background:white;border:1px solid #DCE5E3;border-radius:8px;padding:32px;box-shadow:0 6px 22px #18363D08;}
.wp-public-home .wp-demo header {display:flex;justify-content:space-between;gap:24px;align-items:center;border-bottom:1px solid #DCE5E3;padding-bottom:22px;}
.wp-public-home .wp-demo h3 {margin:0;font-size:19px;}
.wp-public-home .wp-demo header p {font-size:14px;margin:5px 0 0;color:#52686D;}
.wp-public-home .wp-match {color:#775617;background:#F6F0DA;padding:6px 10px;font-size:13px;white-space:nowrap;}
.wp-public-home .wp-evidence {display:grid;grid-template-columns:1fr 1fr;gap:40px;padding-top:28px;}
.wp-public-home .wp-evidence h4 {font-size:12px;color:#075665;margin:0 0 18px;}
.wp-public-home .wp-evidence .wp-watch h4 {color:#865C20;}
.wp-public-home ul {list-style:none;padding:0;margin:0;}
.wp-public-home li {font-size:16px;line-height:1.6;margin:0 0 12px;padding-left:25px;position:relative;}
.wp-public-home li::before {content:'\2713';position:absolute;left:0;color:#075665;}
.wp-public-home .wp-watch li::before {content:'\25B3';color:#865C20;}
.wp-public-home .wp-verdict {border-top:1px solid #DCE5E3;margin-top:20px;padding-top:22px;}
.wp-public-home .wp-verdict p {margin:8px 0 0;font-size:16px;}
.wp-public-home .wp-career {display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center;}
.wp-public-home .wp-context {text-align:center;line-height:1.9;padding:20px 0;}
.wp-public-home .wp-context blockquote {font-family:Georgia,serif;font-size:24px;border:0;margin:0;color:#18363D;padding:0;}
.wp-public-home .wp-context .wp-arrow {font-size:26px;color:#6D8C90;margin:16px 0;}
.wp-public-home .wp-context p {font-size:16px;color:#47686E;}
.wp-public-home .wp-closing {text-align:center;}
.wp-public-home .wp-closing h2 {max-width:800px;margin:0 auto 28px;}
.wp-public-home .wp-trust {font-size:14px;color:#52686D;margin-top:20px;}
.wp-public-home .wp-auth-intro {text-align:center;scroll-margin-top:80px;padding-bottom:10px;}
.stMainBlockContainer:has(.wp-public-home) [data-testid="stTabs"],
.stMainBlockContainer:has(.wp-public-home) .st-key-google_oidc_login {max-width:600px;margin-inline:auto;width:100%;}
.stMainBlockContainer:has(.wp-public-home) [data-testid="stWidgetLabel"] p,
.stMainBlockContainer:has(.wp-public-home) [role="tab"],
.stMainBlockContainer:has(.wp-public-home) [data-testid="stExpander"] summary {color:#18363D;}
.stMainBlockContainer:has(.wp-public-home) [data-testid="stExpander"] [data-testid="stMarkdownContainer"] {color:#18363D;}
.stMainBlockContainer:has(.wp-public-home) [data-testid="stForm"] {border-color:#DCE5E3;}
.stMainBlockContainer:has(.wp-public-home) [data-testid="stTextInputRootElement"],
.stMainBlockContainer:has(.wp-public-home) [data-testid="stTextInput"] input,
.stMainBlockContainer:has(.wp-public-home) [data-testid="stTextInput"] button {background:white;color:#18363D;}
.stMainBlockContainer:has(.wp-public-home) [data-testid="stTextInputRootElement"] {border-color:#94B2B3;}
.stMainBlockContainer:has(.wp-public-home) .st-key-google_oidc_login button,
.stMainBlockContainer:has(.wp-public-home) [data-testid="stFormSubmitButton"] button {background:#075665;color:white;border-color:#075665;}
@media(max-width:800px) {
 .wp-public-home .wp-hero {gap:24px;}
 .wp-public-home .wp-hero h2 {font-size:42px;}
 .wp-public-home .wp-steps {gap:12px;}
 .wp-public-home .wp-step {padding:20px;}
}
@media(max-width:600px) {
 .stMainBlockContainer:has(.wp-public-home) {padding-top:5rem;}
 .wp-public-home .wp-hero,.wp-public-home .wp-contrast,.wp-public-home .wp-steps,
 .wp-public-home .wp-career,.wp-public-home .wp-evidence {grid-template-columns:minmax(0,1fr);gap:24px;}
 .wp-public-home .wp-hero {padding-top:32px;}
 .wp-public-home .wp-hero h2 {font-size:38px;}
 .wp-public-home h2 {font-size:30px;}
 .wp-public-home .wp-band {padding:36px 0;}
 .wp-public-home .wp-demo {padding:22px;}
 .wp-public-home .wp-demo header {align-items:flex-start;flex-direction:column;gap:12px;}
 .wp-public-home .wp-nav a {font-size:14px;max-width:145px;text-align:right;}
 .wp-public-home .wp-actions {gap:18px;}
}
</style>
""")
    # All markup/copy is static. Only our bundled PNG is interpolated.
    st.html("""
<main class="wp-public-home">
  <nav class="wp-nav" aria-label="WorkPilot public navigation">
    <h1>WorkPilot</h1><a href="#workpilot-auth" target="_self">I already have an account</a>
  </nav>
  <section class="wp-hero" aria-labelledby="wp-hero-title">
    <div>
      <p class="wp-eyebrow">WORKPILOT</p>
      <h2 id="wp-hero-title">Finding a job<br>shouldn't become<br>a second job.</h2>
      <p>There are hundreds of jobs out there.<br>Most of them don't deserve your attention.</p>
      <p>WorkPilot learns how you work, keeps an eye on the market, and shows you what's worth a closer look.</p>
      <div class="wp-actions"><a class="wp-primary" href="#workpilot-auth" target="_self">Start with my career</a></div>
    </div>
    <figure>
      <p class="wp-eyebrow">LESS NOISE. MORE ATTENTION.</p>
      <img class="wp-diagram" src="data:image/png;base64,""" + diagram + """" alt="Illustrative example: 385 jobs in the market, 40 recently seen, 10 worth analysing, 3 worth your attention.">
      <figcaption>Illustrative example only. Not live market counts or promised results.</figcaption>
    </figure>
  </section>
  <section class="wp-band wp-contrast">
    <div><p class="wp-eyebrow">MORE JOBS &ne; BETTER SEARCH</p><p>Job boards help you find jobs.</p></div>
    <h2>WorkPilot helps you decide<br>which ones deserve your time.</h2>
  </section>
  <section class="wp-band wp-steps" aria-label="Understand, filter, decide">
    <article class="wp-step"><span class="wp-number">01 / UNDERSTAND</span><h3>Tell WorkPilot how you actually work.</h3><p>Not just your job title.<br>What you do. What you solve.<br>What people rely on you for.</p></article>
    <article class="wp-step"><span class="wp-number">02 / FILTER</span><h3>The market, through your context.</h3><p>WorkPilot compares the market with the professional you actually are.</p><p>Not just keywords against keywords.</p></article>
    <article class="wp-step"><span class="wp-number">03 / DECIDE</span><h3>See what fits.<br>See what doesn't. See why.</h3><p>You make the career decision.</p></article>
  </section>
  <section class="wp-band">
    <div class="wp-demo-intro"><p class="wp-eyebrow">A CLOSER LOOK</p><h2>Not just a match.<br>A reason to pay attention.</h2><p>Illustrative opportunity. Not a live vacancy or a personal assessment.</p></div>
    <article class="wp-demo" aria-label="Illustrative opportunity">
      <header><div><h3>TECHNICAL SUPPORT SPECIALIST</h3><p>Enterprise SaaS</p></div><span class="wp-match">Potential match</span></header>
      <div class="wp-evidence">
        <div><h4>WHY IT'S WORTH A LOOK</h4><ul><li>Strong overlap with customer problem solving</li><li>Experience working across support systems</li><li>Relevant stakeholder communication</li></ul></div>
        <div class="wp-watch"><h4>WATCH OUT FOR</h4><ul><li>Role asks for deeper API troubleshooting</li><li>Some ownership expectations are above your current evidence</li></ul></div>
      </div>
      <div class="wp-verdict"><strong>WorkPilot's view</strong><p>Worth a closer look. You have enough overlap to compete,<br>but there are meaningful gaps to consider.</p></div>
    </article>
  </section>
  <section class="wp-band wp-career">
    <div><p class="wp-eyebrow">YOUR CV ISN'T YOUR WHOLE CAREER.</p><h2>More than the document.<br>The professional behind it.</h2><p>A CV is a document you wrote for a purpose.</p><p>Your career is everything you've actually done, solved, learned and been trusted with.</p><p><strong>WorkPilot starts there.</strong></p></div>
    <div class="wp-context"><blockquote>&ldquo;I work in customer support&rdquo;</blockquote><div class="wp-arrow" aria-hidden="true">&darr;</div><p>customers &middot; systems &middot; escalation<br>problem solving &middot; communication<br>decisions &middot; evidence &middot; outcomes</p><div class="wp-arrow" aria-hidden="true">&darr;</div><strong>YOUR PROFESSIONAL CONTEXT</strong></div>
  </section>
  <section class="wp-band wp-closing"><h2>You take care of your career.<br>WorkPilot takes care of the work around it.</h2><a class="wp-primary" href="#workpilot-auth" target="_self">Start with my career</a><p class="wp-trust">No auto-apply.<br>No career decisions made for you.</p></section>
  <section class="wp-band wp-auth-intro" id="workpilot-auth" aria-labelledby="wp-auth-title"><h2 id="wp-auth-title">Start with your career</h2><p>Create your WorkPilot account and tell us how you actually work.</p></section>
</main>
""")
