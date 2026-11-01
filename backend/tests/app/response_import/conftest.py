import pytest

from backend.config import settings
from tests.app.registration.conftest import memory_jobs  # noqa: F401


@pytest.fixture(autouse=True)
def import_switched_on(monkeypatch, memory_jobs):  # noqa: F811
    """CSV_IMPORT_ENABLED and the question-type switches are on for these tests
    (the switch tests turn the first one off); jobs queue in memory."""
    for name in (
        "CSV_IMPORT_ENABLED",
        "NEW_QUESTION_TYPES_ENABLED",
        "ADDRESS_QUESTION_ENABLED",
        "SIGNATURE_QUESTION_ENABLED",
        "FIELD_RULES_ENABLED",
        "CHOICE_LOGIC_ENABLED",
    ):
        monkeypatch.setattr(settings, name, True)
    return memory_jobs
