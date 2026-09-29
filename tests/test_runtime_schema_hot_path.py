from pathlib import Path


def test_runtime_hot_paths_do_not_create_database_schema():
    forbidden = {
        "services/auth_rate_limiter.py":
            "create_auth_login_failure_schema",
        "services/account_action_rate_limiter.py":
            "create_account_action_request_schema",
        "services/security_audit_repository.py":
            "create_security_audit_schema",
    }

    for filename, symbol in forbidden.items():
        source = Path(filename).read_text(
            encoding="utf-8"
        )

        assert symbol not in source, (
            f"{filename} must not perform schema DDL "
            f"during normal runtime operations."
        )
