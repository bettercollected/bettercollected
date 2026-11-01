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


@pytest.fixture()
def sources_on(monkeypatch):
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", True)
