"""Allowlisted diagnostics; never stringify an untrusted exception or response."""
from contextlib import contextmanager
from functools import wraps
import logging

from requests import RequestException, Timeout
from openai import APIError, APITimeoutError, RateLimitError
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from oauthlib.oauth2 import OAuth2Error


class ProviderFailure(RuntimeError):
    def __init__(self, code):
        self.code = code if code in {'provider_timeout', 'provider_error', 'provider_rate_limited'} else 'provider_error'
        super().__init__(self.code)


class ProviderRateLimit(ProviderFailure):
    def __init__(self):
        super().__init__('provider_rate_limited')


def failure_code(error):
    if isinstance(error, ProviderFailure):
        return error.code
    if isinstance(error, RateLimitError):
        return 'provider_rate_limited'
    if isinstance(error, (TimeoutError, Timeout, APITimeoutError)):
        return 'provider_timeout'
    if isinstance(error, (RequestException, APIError, GoogleAuthError, HttpError, OAuth2Error)):
        return 'provider_error'
    return 'operation_failed'


def log_failure(logger, stage, error):
    # Stage names are constants, never exception attributes or user input.
    stages = {'ai_generation', 'profile_generation', 'job_analysis', 'job_enrichment',
              'gmail_oauth', 'gmail_sync', 'gmail_background', 'gmail_processing'}
    stage = stage if stage in stages else 'provider_operation'
    kind = type(error).__name__ if type(error) in (TypeError, ValueError, KeyError,
        AttributeError, RuntimeError, AssertionError) else 'ExternalOrOperationalError'
    logger.warning('operation_failed stage=%s code=%s kind=%s', stage, failure_code(error), kind)


@contextmanager
def provider_boundary(stage):
    from services.ai.openai_semantic_interpreter import _private_transport_logs
    with _private_transport_logs():
        try:
            yield
        except RateLimitError as error:
            log_failure(logging.getLogger(__name__), stage, error)
            raise ProviderRateLimit() from None
        except (RequestException, APIError, GoogleAuthError, HttpError, OAuth2Error, TimeoutError) as error:
            code = failure_code(error)
            log_failure(logging.getLogger(__name__), stage, error)
            raise ProviderFailure(code) from None


def provider_operation(stage):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            with provider_boundary(stage):
                return function(*args, **kwargs)
        return call
    return decorate
