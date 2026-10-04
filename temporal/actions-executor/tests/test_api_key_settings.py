"""The key sent to the backend's internal job routes has no usable default:
unset, empty or the old public placeholder all mean "not configured"."""

import pytest

from settings.application import ApplicationSettings, log_if_api_key_missing


@pytest.mark.parametrize("value", [None, "", "  ", "random_api_key"])
def test_unset_empty_or_placeholder_is_not_configured(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", value)
    current = ApplicationSettings(_env_file=None)
    assert current.api_key == ""
    assert log_if_api_key_missing(current) is False


def test_configured_key_is_kept(monkeypatch):
    monkeypatch.setenv("API_KEY", "a-generated-key")
    current = ApplicationSettings(_env_file=None)
    assert current.api_key == "a-generated-key"
    assert log_if_api_key_missing(current) is True
