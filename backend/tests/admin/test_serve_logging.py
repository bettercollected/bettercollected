"""``python -m backend.admin.serve`` writes its own log lines to the container log.

The ``backend`` package carries a ``NullHandler``, so without a handler of its own
the service's warnings (the bare-gate notice, gate refusals, mail that could not be
sent, loop failures) were dropped silently: a container log was the only place an
operator could see them."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Starts the service with uvicorn stubbed out, in a fresh process (logging is
# process-wide), without the portal's settings: the bare gate logs one warning.
PROGRAM = (
    "import uvicorn\n"
    "uvicorn.run = lambda *a, **k: None\n"
    "from backend.admin import serve\n"
    "serve.main()\n"
    "import logging\n"
    "logging.getLogger('backend.admin.security.mailer').warning('admin mail not sent (probe)')\n"
)


def run_serve(extra=None):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ADMIN_", "SETTINGS_MASTER_KEY", "PLATFORM_ADMIN_EMAILS"))
    }
    env.update(extra or {})
    return subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_the_bare_gate_warning_and_later_warnings_reach_the_log():
    result = run_serve()
    assert result.returncode == 0, result.stderr[-2000:]
    assert "admin portal disabled, serving only the health check" in result.stderr
    assert "ADMIN_DATABASE_URL" in result.stderr
    assert "admin mail not sent (probe)" in result.stderr

