from types import SimpleNamespace

import services.streamlit_oidc as oidc


def test_oidc_absent_fails_closed(monkeypatch):
    monkeypatch.setattr(
        oidc.st,
        "user",
        SimpleNamespace(),
    )

    assert oidc.oidc_available() is False
    assert oidc.oidc_logged_in() is False


def test_oidc_configured_logged_out(monkeypatch):
    monkeypatch.setattr(
        oidc.st,
        "user",
        SimpleNamespace(
            is_logged_in=False,
        ),
    )

    assert oidc.oidc_available() is True
    assert oidc.oidc_logged_in() is False


def test_oidc_configured_logged_in(monkeypatch):
    monkeypatch.setattr(
        oidc.st,
        "user",
        SimpleNamespace(
            is_logged_in=True,
        ),
    )

    assert oidc.oidc_available() is True
    assert oidc.oidc_logged_in() is True


def test_runtime_has_no_unsafe_direct_oidc_access():
    from pathlib import Path

    for filename in (
        "streamlit_app.py",
        "pages/0_Login.py",
        "services/session_auth.py",
    ):
        source = Path(filename).read_text(
            encoding="utf-8"
        )

        assert "st.user.is_logged_in" not in source


def test_cookie_resolution_precedes_navigation_and_preserves_oidc_route():
    from pathlib import Path
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    authentication = source.index("authenticated_user = get_authenticated_user()")
    assert authentication < source.index("st.navigation(")
    assert authentication < source.index("run_page(navigation)")
    assert "oidc_logged_in()" in source[authentication:]
    assert "st.switch_page(" in source[authentication:]
    assert 'if st.session_state.get("current_user") is None:' not in source


def test_private_shell_revalidates_cached_identity():
    from pathlib import Path

    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "# Never authorize the private shell "
        "from session_state alone."
        in source
    )

    assert (
        "authenticated_user = "
        "get_authenticated_user()"
        in source
    )
