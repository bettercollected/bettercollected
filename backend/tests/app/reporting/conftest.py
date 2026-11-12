import pytest

from backend.app.container import container
from backend.config import settings


@pytest.fixture(autouse=True)
def fresh_report_state():
    """The service is one instance per process: the aggregates and catalogues
    an earlier test cached are not this test's."""
    service = container.report_service()
    service._cache.clear()
    service._catalogues.clear()


@pytest.fixture(autouse=True)
def new_question_types(monkeypatch):
    # the currency question the tests report on is a gated type
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)


@pytest.fixture()
def reporting_on(monkeypatch):
    monkeypatch.setattr(settings.reporting, "ENABLED", True)


@pytest.fixture()
def form_access_on(monkeypatch):
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
