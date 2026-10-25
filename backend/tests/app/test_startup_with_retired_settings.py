"""A deployment that still sets the removed marketing tracker's variables
(BREVO_TRACKER_KEY, BREVO_TRACKER_API_URL, BREVO_CONTACTS_API_KEY) keeps
starting: no service reads them any more and the settings inventory lists
them as retired, so leaving them set is harmless.

The case boots the real application in a fresh process, as a deployment
does, with the three variables set to dummy values."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
LEFTOVERS = {
    "BREVO_TRACKER_KEY": "DUMMY-tracker-key",
    "BREVO_TRACKER_API_URL": "https://tracker.example.test/events",
    "BREVO_CONTACTS_API_KEY": "DUMMY-contacts-key",
}

API = """
from fastapi.testclient import TestClient

from backend.app import get_application
from backend.config import settings

assert not hasattr(settings, "brevo_settings")
with TestClient(get_application()) as client:
    print("served:", client.get("/").status_code)
print("started")
"""


def test_the_api_starts_with_the_former_marketing_variables_still_set():
    env = dict(os.environ, DB_AUTO_MIGRATE="false", **LEFTOVERS)
    result = subprocess.run(
        [sys.executable, "-c", API],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert "started" in result.stdout
