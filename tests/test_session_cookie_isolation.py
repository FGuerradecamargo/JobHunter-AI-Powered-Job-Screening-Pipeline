"""Real cookie manager, independent browser jars, one imported auth module."""
import importlib
import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest
import streamlit as st
import streamlit.runtime.scriptrunner as runner

from tests.test_session_auth_security import AttrDict, FakeConnection


@pytest.fixture
def browsers(monkeypatch):
    from services import application_bootstrap

    monkeypatch.setattr(application_bootstrap, 'bootstrap_application', lambda: None)
    monkeypatch.setenv('SESSION_COOKIE_KEY', 'isolated-browser-test-only')
    connection = FakeConnection()
    users = {key: SimpleNamespace(id=key, display_name=key) for key in ('a', 'b')}
    contexts = {key: SimpleNamespace(state=AttrDict(), jar={}, cursors={}, ready=True)
                for key in users}
    current = [contexts['a']]

    def activate(key):
        current[0] = contexts[key]
        current[0].cursors = {}  # Streamlit resets cursors on each script rerun.
        monkeypatch.setattr(st, 'session_state', current[0].state)

    def component(*, queue, saveOnly, key):
        browser = current[0]
        if not browser.ready:
            return None
        for name, spec in queue.items():
            if spec['value'] is None:
                browser.jar.pop(name, None)
            else:
                browser.jar[name] = spec['value']
        return '; '.join(quote(k) + '=' + quote(v) for k, v in browser.jar.items())

    cm = importlib.import_module('streamlit_cookies_manager.cookie_manager')
    monkeypatch.setattr(cm, '_component_func', component)
    monkeypatch.setattr(runner, 'get_script_run_ctx', lambda: current[0])
    activate('a')
    spec = importlib.util.spec_from_file_location('isolated_auth',
        Path(__file__).resolve().parents[1] / 'services/session_auth.py')
    auth = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth)

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(auth, 'get_connection', get_connection)
    monkeypatch.setattr(auth, 'UserRepository', lambda: SimpleNamespace(
        get_by_id=lambda user_id: users.get(user_id)))
    return SimpleNamespace(auth=auth, activate=activate, contexts=contexts,
                           users=users, connection=connection)


def test_blank_browser_never_inherits_other_browser_identity(browsers):
    b = browsers
    b.auth.login_user(b.users['a'])
    b.activate('a')
    assert b.auth.get_authenticated_user() is b.users['a']
    b.activate('b')
    assert not b.contexts['b'].jar
    assert b.auth.get_authenticated_user() is None
    assert 'current_user' not in b.contexts['b'].state


def test_interleaved_login_rerun_logout_and_revocation(browsers):
    b = browsers
    b.auth.login_user(b.users['a'])
    b.activate('b')
    assert b.auth.get_authenticated_user() is None
    b.auth.login_user(b.users['b'])
    b_cookie = dict(b.contexts['b'].jar)
    for key in ('a', 'b', 'a', 'b'):
        b.activate(key)
        assert b.auth.get_authenticated_user() is b.users[key]
        assert b.auth.get_authenticated_user() is b.users[key]
    assert len(b.connection.sessions) == 2
    b.activate('a')
    b.auth.logout_user()
    assert b.contexts['b'].jar == b_cookie
    assert {row['user_id'] for row in b.connection.sessions.values()} == {'b'}
    b.activate('a')
    assert b.auth.get_authenticated_user() is None
    b.auth.login_user(b.users['a'])
    b.activate('b')
    assert b.auth.get_authenticated_user() is b.users['b']
    b.auth.revoke_user_sessions('b')
    b.activate('b')
    assert b.auth.get_authenticated_user() is None
    b.activate('a')
    assert b.auth.get_authenticated_user() is b.users['a']


def test_changed_browser_cookie_is_read_on_next_rerun(browsers):
    b = browsers
    b.auth.login_user(b.users['a'])
    b.activate('a')
    assert b.auth.get_authenticated_user() is b.users['a']
    b.contexts['a'].jar.clear()
    b.activate('a')
    assert b.auth.get_authenticated_user() is None


@pytest.mark.parametrize('field', ['expires_at', 'last_activity_at'])
def test_expiring_b_does_not_clear_or_revoke_a(browsers, field):
    b = browsers
    b.auth.login_user(b.users['a'])
    b.activate('b')
    b.auth.login_user(b.users['b'])
    for row in b.connection.sessions.values():
        if row['user_id'] == 'b':
            row[field] = '2000-01-01T00:00:00+00:00'
    b.activate('b')
    assert b.auth.get_authenticated_user() is None
    assert 'current_user' not in b.contexts['b'].state
    assert b.contexts['b'].state['reauthentication_required'] is True
    b.activate('a')
    assert b.auth.get_authenticated_user() is b.users['a']
    token = b.auth._get_cookies().get(b.auth.SESSION_COOKIE)
    assert token not in b.connection.sessions
    assert b.auth._hash_session_token(token) in b.connection.sessions
    assert token not in b.contexts['a'].jar.values()


def test_cookie_readiness_stops_before_authentication_or_login(browsers, monkeypatch):
    from streamlit.runtime.scriptrunner import StopException
    b = browsers
    b.auth.login_user(b.users['a'])
    b.activate('b')
    b.contexts['b'].ready = False

    def stop():
        raise StopException()

    monkeypatch.setattr(st, 'stop', stop)
    for action in (b.auth.get_authenticated_user, lambda: b.auth.login_user(b.users['b'])):
        with pytest.raises(StopException):
            action()
    assert {row['user_id'] for row in b.connection.sessions.values()} == {'a'}
    assert 'current_user' not in b.contexts['b'].state
    b.contexts['b'].ready = True
    b.activate('b')
    assert b.auth.get_authenticated_user() is None


def test_no_streamlit_context_fails_closed(browsers, monkeypatch):
    monkeypatch.setattr(browsers.auth, 'get_script_run_ctx', lambda: None)
    with pytest.raises(RuntimeError, match='Streamlit session context'):
        browsers.auth.get_authenticated_user()


def test_real_streamlit_reruns_rebuild_manager_without_duplicate_components(monkeypatch):
    from streamlit.testing.v1 import AppTest
    cm = importlib.import_module('streamlit_cookies_manager.cookie_manager')
    real_component = cm._component_func
    calls = []

    def component(**kwargs):
        # Exercise Streamlit's actual component registration, but simulate an
        # empty browser cookie response (AppTest has no JavaScript frontend).
        real_component(**kwargs)
        calls.append(kwargs['key'])
        return ''

    monkeypatch.setattr(cm, '_component_func', component)
    script = '''
import streamlit as st
from services.session_auth import _get_cookies
manager = _get_cookies()
assert _get_cookies() is manager
assert manager is not st.session_state.get('previous_manager')
st.session_state.previous_manager = manager
st.button('Another rerun')
'''
    a, b = AppTest.from_string(script), AppTest.from_string(script)
    for app in (a, b, a, b):
        app.run()
        assert not app.exception
    assert len(calls) == 4
    assert a.session_state['previous_manager'] is not b.session_state['previous_manager']
