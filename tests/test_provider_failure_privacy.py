import logging
import traceback
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
import requests
from openai import APIError, RateLimitError

from services.provider_failure import ProviderFailure, ProviderRateLimit, failure_code, provider_boundary
from services.ai.openai_client import OpenAIClient
from services.gmail_background_sync_service import GmailBackgroundSyncService
from services.gmail_job_processor import GmailJobProcessor
from tests.test_gmail_oauth_navigation import callback
from tests.test_candidate_job_analysis_trace_wiring import _build_service, SOURCE_ROW
import services.candidate_job_analysis_service as analysis_module


HOSTILE = ('sk-FAKE_PRIVATE_KEY Authorization: Bearer FAKE_TOKEN\n'
           'PRIVATE_CV_SENTINEL PRIVATE_EMAIL_SENTINEL {"provider_payload":"PRIVATE_JSON"}\n'
           'Traceback (most recent call last): PRIVATE_TRACE')


def fail(*args, **kwargs):
    raise requests.Timeout(HOSTILE)


def assert_private_free(value):
    for marker in ('FAKE_PRIVATE_KEY', 'FAKE_TOKEN', 'PRIVATE_CV', 'PRIVATE_EMAIL', 'PRIVATE_JSON', 'PRIVATE_TRACE'):
        assert marker not in str(value)


def test_openai_transport_suppresses_payload_logs_and_exception_chain(caplog, capsys):
    client = object.__new__(OpenAIClient)
    client.model = 'fake-model'
    def generate(**kwargs):
        logging.getLogger('openai._base_client').debug(HOSTILE)
        raise APIError(HOSTILE, request=httpx.Request('POST', 'https://example.invalid'), body={'private': HOSTILE})
    client.client = SimpleNamespace(responses=SimpleNamespace(create=generate))
    with caplog.at_level(logging.DEBUG), pytest.raises(ProviderFailure) as caught:
        client.generate('FAKE_PROMPT')
    assert str(caught.value) == 'provider_error'
    assert_private_free(''.join(traceback.format_exception(caught.type, caught.value, caught.tb)))
    assert_private_free(caplog.text + str(capsys.readouterr()))
    assert 'stage=ai_generation code=provider_error' in caplog.text


def test_programmer_errors_are_not_swallowed_by_transport_boundary():
    with pytest.raises(TypeError, match='programming mistake'):
        with provider_boundary('ai_generation'):
            raise TypeError('programming mistake')


def test_rate_limit_semantics_preserved():
    with pytest.raises(ProviderRateLimit) as caught:
        with provider_boundary('ai_generation'):
            raise RateLimitError(HOSTILE, response=httpx.Response(429,
                request=httpx.Request('POST', 'https://example.invalid')), body=None)
    assert failure_code(caught.value) == 'provider_rate_limited'


@pytest.mark.parametrize('stage', ['preparation', 'batch_ai', 'persistence'])
def test_analysis_failures_are_sanitized_before_persistence_and_return(monkeypatch, caplog, capsys, stage):
    service = _build_service(monkeypatch, ai_error=requests.Timeout(HOSTILE) if stage == 'batch_ai' else None)
    failures = []
    monkeypatch.setattr(analysis_module, 'append_candidate_job_analysis_run', lambda **kw: failures.append(kw))
    if stage == 'preparation':
        service.job_profile_manager.get_or_create = fail
    if stage == 'persistence':
        monkeypatch.setattr(analysis_module, 'save_candidate_job_analysis_with_run', fail)
    result = service._run_candidate_job_analysis(candidate_id='candidate-a', source_rows=[dict(SOURCE_ROW)],
        preserve_existing_lifecycle=True, scan_id='fake-scan', run_mode='reanalysis')
    assert failures and result['failed'] == 1
    assert failures[0]['error_text'] == 'provider_timeout'
    assert result['errors'][0]['error'] == 'provider_timeout'
    assert_private_free((failures, result, caplog.text, capsys.readouterr()))


def test_gmail_background_result_and_logs_are_sanitized(caplog, capsys):
    service = object.__new__(GmailBackgroundSyncService)
    service._connection_repository = Mock()
    service._connection_repository.list_connected_user_ids.return_value = ['fake-owner']
    service._sync_service = SimpleNamespace(sync_recent_job_alerts=fail)
    result = service.run()
    assert result.users_failed == 1 and result.results[0].error == 'provider_timeout'
    assert_private_free((result, caplog.text, capsys.readouterr()))
    assert 'gmail_background' in caplog.text


def test_gmail_processing_persisted_error_is_sanitized(monkeypatch, caplog, capsys):
    messages = Mock()
    messages.list_pending.return_value = [{'gmail_message_id': 'fake-message', 'raw_html': 'fake'}]
    monkeypatch.setattr('services.gmail_job_processor.extract_jobs_from_email', fail)
    result = GmailJobProcessor(messages, Mock()).process_pending_messages('fake-owner')
    assert result.messages_failed == 1
    assert messages.mark_failed.call_args.kwargs['error_message'] == 'provider_timeout'
    assert_private_free((messages.mark_failed.call_args, result, caplog.text, capsys.readouterr()))


@pytest.mark.parametrize('provider_callback', [True, False])
def test_gmail_callback_ui_and_logs_never_echo_provider_payload(callback, provider_callback):
    if provider_callback:
        callback['st'].query_params.update(error='access_denied', error_description=HOSTILE)
    else:
        callback['oauth_service'].exchange_authorization_code.side_effect = requests.Timeout(HOSTILE)
    callback['handle_oauth_callback']()
    assert_private_free(callback['st'].error.call_args_list)
    assert_private_free(callback['logger'].mock_calls)
    callback['logger'].exception.assert_not_called()
    callback['st'].switch_page.assert_not_called()


def test_job_enrichment_does_not_print_private_url_or_exception(monkeypatch, caplog, capsys):
    from services.job_details_fetcher import fetch_job_description
    monkeypatch.setattr('services.job_details_fetcher.requests.get', fail)
    assert fetch_job_description('https://example.invalid/?key=FAKE_PRIVATE_KEY') is None
    assert_private_free((caplog.text, capsys.readouterr()))


def test_failure_code_never_calls_exception_str():
    class Hostile(Exception):
        def __str__(self):
            raise AssertionError('Do not inspect payloads')
    assert failure_code(Hostile()) == 'operation_failed'


def test_gmail_oauth_transport_masks_external_failure(monkeypatch, caplog):
    from services.gmail_oauth_service import GmailOAuthService
    service = GmailOAuthService('fake-id', 'fake-key', 'https://example.invalid/Sources')
    monkeypatch.setattr(service, '_create_flow', lambda **kw: SimpleNamespace(fetch_token=fail))
    with pytest.raises(ProviderFailure) as caught:
        service.exchange_authorization_code('fake-code', 'fake-state', 'fake-verifier')
    assert str(caught.value) == 'provider_timeout'
    assert_private_free(caplog.text)


@pytest.mark.parametrize('parse_error', [False, True])
def test_cv_failure_result_is_safe_even_for_hostile_parser_exception(caplog, parse_error):
    from services.tailored_cv_generation_service import TailoredCVGenerationService
    from services.tailored_cv_parser import TailoredCVParseError
    from tests.test_tailored_cv_generation_service import FakeGeneratorClient, _context
    error = TailoredCVParseError(HOSTILE) if parse_error else requests.Timeout(HOSTILE)
    result = TailoredCVGenerationService(FakeGeneratorClient(error=error)).generate(_context())
    assert result.error_code in {'invalid_generator_output', 'generator_client_error'}
    assert_private_free((result, caplog.text))
