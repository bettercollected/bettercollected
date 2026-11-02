import pytest

from backend.config import settings


@pytest.fixture()
def sections_on(monkeypatch):
    monkeypatch.setattr(settings, "REUSABLE_SECTIONS_ENABLED", True)
    # what a section may hold is gated by the same switches as a form
    for flag in (
        "FIELD_RULES_ENABLED",
        "LAYOUT_CONTAINERS_ENABLED",
        "NEW_QUESTION_TYPES_ENABLED",
        "CHOICE_LOGIC_ENABLED",
        "OPTION_SOURCES_ENABLED",
    ):
        monkeypatch.setattr(settings, flag, True)
