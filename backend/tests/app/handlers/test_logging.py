"""Tracebacks in the logs never show local variable values."""

import copy
import io

import pytest
from loguru import logger

import backend.app.handlers as handlers


@pytest.fixture()
def isolated_logger(monkeypatch):
    """An independent copy of the logger for init_logging to configure, so the
    global logger and its handlers are left exactly as they were."""
    # a logger with sinks (pytest's capture streams) can't be copied: detach
    # them for the copy only, then put the very same handlers back
    core = logger._core
    attached = core.handlers
    core.handlers = {}
    try:
        own = copy.deepcopy(logger)
    finally:
        core.handlers = attached
    monkeypatch.setattr(handlers, "logger", own)
    yield own
    own.remove()


def test_logged_exceptions_do_not_print_local_variables(monkeypatch, isolated_logger):
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    handlers.init_logging()
    secret_value = "answer-from-a-respondent-8841"
    try:
        secret_value.missing  # diagnose would print the value next to this line
    except AttributeError:
        isolated_logger.exception("failed while handling {}", "a request")
    text = out.getvalue()
    assert "AttributeError" in text
    assert secret_value not in text


def test_the_global_logger_keeps_its_handlers(monkeypatch, isolated_logger):
    before = dict(logger._core.handlers)
    monkeypatch.setattr("sys.stdout", io.StringIO())
    handlers.init_logging()
    assert logger._core.handlers == before
