from pathlib import Path


def test_accepted_runtime_exposes_only_explicit_product_state_choices():
    source = Path("app.py").read_text(encoding="utf-8")

    assert 'if view.state == "accepted":' in source
    assert '"Keep searching"' in source
    assert '"Switch to Career"' in source
    assert '"End subscription"' in source

    assert "HiredNextAction.KEEP_SEARCHING" in source
    assert "HiredNextAction.SWITCH_TO_CAREER" in source
    assert "HiredNextAction.END_SUBSCRIPTION" in source

    assert "HiredTransitionService(" in source


def test_accepted_runtime_does_not_confirm_access_or_fake_billing():
    source = Path("app.py").read_text(encoding="utf-8")

    assert "ConfirmedProductAccessService" not in source
    assert ".confirm_read_only(" not in source
    assert (
        "Your access has not been changed until billing confirms it."
        in source
    )
