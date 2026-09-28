# WorkPilot V1 Frontend Cutover

Base: `91aa69f`, branch `feature/workpilot-v1-implementation`.

## Presentation Decisions

- `components/workpilot_ui.py` and `components/workpilot.css` provide shared typography, headers, badges, empty states and responsive styling.
- `streamlit_app.py` registers Dashboard, Jobs, Applications, Improvements, Profile and Settings. Product-mode restrictions remain authoritative. The Sources route remains registered but hidden from primary navigation to preserve OAuth callbacks.
- `components/dashboard.py` reads candidate-scoped application counts, official CandidateProfile and CandidateMarket priorities. It does not create recommendations or change product state.
- `pages/5_Applications.py` invokes the existing application workspace in `app.py`. Lifecycle confirmation, export, interview rounds and outcomes remain unchanged.
- `pages/6_Settings.py` exposes account information, supported product-mode controls, subscription intent information, source management and logout. No billing integration is claimed.
- Profile Overview renders the official snapshot/checkpoint, not the old parallel career-positioning summary. Existing evidence editors remain available. Checkpoint strength labels are presented directly rather than inferred from missing negative/transferability flags.
- Jobs uses the same HiringCase with explicit `You -> Company` and `Job -> You` dimensions. Improvements retains official NOW/NEXT/WATCH and BUILD/PROVE/EXPLORE data.
- Public Home and Login use the shared theme without seasonal decoration. Onboarding retains its durable state, stepper and contextual panels.

## Browser Recovery Fix

A fresh browser session can recover its authenticated cookie while the shell still has only public routes registered. The new Dashboard's private page links exposed this ordering issue on refresh.

The shell now marks its presentation navigation phase. After authentication has been independently verified, the public-page render returns to the shell, which rebuilds private navigation before rendering the Dashboard. This flag only controls rendering; it cannot authenticate or authorize anyone.

Regression coverage exercises the deferred private render. Real browser checks verify refresh and second-tab recovery. Recovery uses the canonical Dashboard; restoring the exact previously selected subpage is not introduced by this change.

## Validation

- Focused UI/authentication suite: 58 passed.
- Final full offline suite: 2150 passed, 2 skipped (257.48 seconds).
- `git diff --check`: passed; only Git's expected LF/CRLF conversion notices.
- Edge headless browser: public Home, password Login, Dashboard, Jobs, Applications, Improvements, Profile, Settings, onboarding entry, refresh and second-tab recovery.
- Search, Career and Read-only navigation verified with independent synthetic accounts. Jobs is unavailable outside Search, and Read-only Profile omits editors.
- All six primary Search pages checked at 1440px and 390px widths; no horizontal overflow. Screenshots inspected.
- SQLite database was created in a disposable temporary directory. Repository dotenv loading was disabled, DATABASE_URL was empty, and external socket/browser requests were blocked.
- Browser fixtures intentionally did not invoke paid search, CV generation, voice, OAuth or providers. Existing offline domain tests cover those integration contracts. Live provider behavior and production deployment appearance still need a separately authorized smoke test.

## Changed Surfaces

Shell and pages: `streamlit_app.py`, `app.py`, `pages/1_Opportunities.py`, `pages/2_Sources.py`, `pages/3_Profile.py`, `pages/4_Improvements.py`, `pages/5_Applications.py`, `pages/6_Settings.py`.

Components: `dashboard.py`, `workpilot_ui.py`, `workpilot.css`, `public_landing.py`, `profile_onboarding.py`, `job_analysis_view.py`.

Tests: `test_workpilot_workspace_ui.py`, `test_public_login_landing.py`, `test_v1_application_interview_runtime.py`.

No backend/domain/database service or schema was changed. No production database or provider was accessed.
