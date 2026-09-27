"""Tracebacks in the logs never show local variable values."""

import io
import sys

from loguru import logger

from backend.app.handlers import init_logging


def test_logged_exceptions_do_not_print_local_variables(monkeypatch):
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    init_logging()
    secret_value = "answer-from-a-respondent-8841"
    try:
        secret_value.missing  # diagnose would print the value next to this line
    except AttributeError:
        logger.exception("failed while handling {}", "a request")
    text = out.getvalue()
    logger.remove()  # the StringIO sink must not outlive this test
    logger.add(sys.stderr)
    assert "AttributeError" in text
    assert secret_value not in text
