import pytest

from backend.config import settings


@pytest.fixture(autouse=True)
def fresh_service_state():
    """The service is one instance per process: what it remembers of a client
    or a source from an earlier test is not this test's."""
    from backend.app.container import container

    service = container.option_source_service()
    service._coarse.clear()
    service._cache.clear()
    service._access.clear()
    service._servable_cache.clear()
    service._items = 0
    # tests run the redaction themselves (test_erasure turns it on where it
    # checks the automatic start)
    service._auto_redact = False
    service._redaction_task = None


@pytest.fixture()
def sources_on(monkeypatch):
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", True)
