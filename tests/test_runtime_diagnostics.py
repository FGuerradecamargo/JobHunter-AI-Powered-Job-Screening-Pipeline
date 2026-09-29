import logging
from unittest.mock import Mock

import pytest

from services.oidc_diagnostics import oidc_call, STAGES
from services.runtime_timing import TimedConnection, timed_block


@pytest.mark.parametrize("stage", sorted(STAGES))
def test_oidc_failure_records_only_stage(caplog, stage):
    caplog.set_level(logging.INFO)
    operation = Mock(side_effect=RuntimeError("private email token secret"))
    with pytest.raises(RuntimeError):
        oidc_call(stage, operation, "private claim")
    assert f"stage={stage} status=failed" in caplog.text
    assert "private" not in caplog.text and "secret" not in caplog.text


def test_query_and_block_timings_hide_sql_and_parameters(caplog):
    caplog.set_level(logging.INFO)
    raw = Mock()
    connection = TimedConnection(raw)
    with timed_block("applications"):
        cursor = connection.execute("SELECT private_content WHERE token=?", ("secret",))
    assert cursor is raw.execute.return_value
    assert "database.query.applications" in caplog.text
    assert "elapsed_ms=" in caplog.text
    assert "private_content" not in caplog.text and "secret" not in caplog.text


def test_fresh_process_emits_safe_diagnostics_without_root_configuration():
    import subprocess
    import sys
    script = '''
from services.runtime_timing import timed_block
from services.oidc_diagnostics import oidc_stage
with timed_block("profile"):
    pass
with oidc_stage("callback"):
    pass
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert "block=profile" in result.stderr
    assert "stage=callback status=completed" in result.stderr
