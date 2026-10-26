"""A stack that still sets the removed error reporter's variables (SENTRY_DSN,
SENTRY_DEBUG) keeps starting: nothing reads them any more and the settings
inventory lists them as retired.

The case boots the app factory in a fresh process, as a deployment does, with
both variables set to dummy values."""

import os
import subprocess
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[2]

PROGRAM = """
import sys

from fastapi.testclient import TestClient

from googleform.app import get_application
from googleform.config import settings

assert not hasattr(settings, "sentry_settings")
assert "sentry_sdk" not in sys.modules
with TestClient(get_application()):
    print("started")
"""


def test_starts_with_the_former_error_reporter_variables_still_set(_postgres_schema):
    env = dict(
        os.environ,
        SENTRY_DSN="https://dummykey@errors.example.test/1",
        SENTRY_DEBUG="true",
    )
    result = subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert "started" in result.stdout, result.stdout
