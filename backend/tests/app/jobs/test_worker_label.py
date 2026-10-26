"""The jobs worker labels its settings heartbeat, so the admin portal's Health page
shows it apart from the API (it reports as the same service, from the same database
role). The label must be set before ``backend.config`` loads the settings, which
starts the heartbeat."""

import importlib.util
from pathlib import Path

from common.settings.loader.source import instance_id


def test_the_worker_sets_its_label_before_the_settings_load(monkeypatch):
    spec = importlib.util.find_spec("backend.jobs.worker")
    source = Path(spec.origin).read_text(encoding="utf-8")
    label = source.index('set_instance_role("jobs")')
    assert label < source.index("from backend.config import settings")
    assert label < source.index("from backend.app.container import container")
    monkeypatch.setattr("socket.gethostname", lambda: "abc123")
    assert instance_id("backend", None, "jobs") == "backend.jobs:abc123"
