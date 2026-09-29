"""Request-local timing. Logs contain static labels, never query text or data."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import logging
from time import perf_counter

logger = logging.getLogger("workpilot.timing")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler())
_page = ContextVar("workpilot_timing_page", default="shell")
_block = ContextVar("workpilot_timing_block", default="runtime")


def log_timing(
    name: str,
    elapsed_ms: float,
    outcome: str = "ok",
) -> None:
    logger.info(
        "runtime_timing page=%s block=%s elapsed_ms=%.2f outcome=%s",
        _page.get(),
        name,
        elapsed_ms,
        outcome,
    )


@contextmanager
def timed_block(name):
    token = _block.set(name)
    start = perf_counter()
    outcome = "ok"
    try:
        yield
    except Exception:
        outcome = "failed"
        raise
    finally:
        log_timing(
            name,
            (perf_counter() - start) * 1000,
            outcome,
        )
        _block.reset(token)


def timed(name):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with timed_block(name):
                return fn(*args, **kwargs)
        return wrapped
    return decorate


def run_page(page):
    token = _page.set(page.title)
    try:
        with timed_block("page"):
            page.run()
    finally:
        _page.reset(token)


def timed_page(name):
    """Fragments rerun outside navigation.run; reestablish their page label."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            token = _page.set(name)
            try:
                with timed_block("fragment"):
                    return fn(*args, **kwargs)
            finally:
                _page.reset(token)
        return wrapped
    return decorate


class TimedConnection:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, *args, **kwargs):
        with timed_block("database.query." + _block.get()):
            return self.connection.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        with timed_block("database.query." + _block.get()):
            return self.connection.executemany(*args, **kwargs)

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.connection.__exit__(*args)
