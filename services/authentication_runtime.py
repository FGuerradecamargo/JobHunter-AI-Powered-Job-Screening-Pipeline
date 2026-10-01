"""Provider-neutral continuation and external-identity runtime boundary."""
from services.streamlit_oidc import oidc_logged_in, logout_oidc_if_logged_in


def authentication_continuation_required() -> bool:
    """Request Login routing for an unfinished flow, never authorization."""
    return oidc_logged_in()


def logout_external_identity_if_active() -> bool:
    return logout_oidc_if_logged_in()
