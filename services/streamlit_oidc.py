from __future__ import annotations

import streamlit as st


_MISSING = object()


def _oidc_login_state():
    """Read Streamlit OIDC state without assuming OIDC is configured.

    With configured OIDC, st.user exposes is_logged_in.
    Without configured OIDC, that attribute may not exist.
    """
    try:
        return getattr(
            st.user,
            "is_logged_in",
            _MISSING,
        )
    except Exception:
        return _MISSING


def oidc_available() -> bool:
    return _oidc_login_state() is not _MISSING


def oidc_logged_in() -> bool:
    state = _oidc_login_state()

    if state is _MISSING:
        return False

    return bool(state)


def logout_oidc_if_logged_in() -> bool:
    if not oidc_logged_in():
        return False

    st.logout()
    return True
