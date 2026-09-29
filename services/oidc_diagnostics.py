"""Allowlisted OIDC stage diagnostics, with no claims, IDs or exception text."""
from contextlib import contextmanager
import logging

logger = logging.getLogger("workpilot.oidc")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler())
STAGES = {"start", "callback", "claims_received", "identity_resolution", "account_register", "account_link", "login_user"}


@contextmanager
def oidc_stage(stage):
    if stage not in STAGES:
        raise ValueError("Unknown authentication stage")
    logger.info("oidc stage=%s status=started", stage)
    try:
        yield
    except Exception:
        logger.warning("oidc stage=%s status=failed", stage)
        raise
    else:
        logger.info("oidc stage=%s status=completed", stage)


def oidc_call(stage, operation, *args, **kwargs):
    with oidc_stage(stage):
        return operation(*args, **kwargs)
