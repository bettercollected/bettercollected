"""The auth service's API is internal (#766): this service's one call into it
carries the shared key."""

from unittest import mock

import pytest

from googleform.app.services import migration_service
from googleform.config import settings


class FakeResponse:
    @staticmethod
    def json():
        return {"users_info": [{"_id": "5f0000000000000000000000"}]}


@pytest.fixture
def sent(monkeypatch):
    get = mock.Mock(return_value=FakeResponse())
    monkeypatch.setattr(migration_service.requests, "get", get)
    return get


@pytest.mark.asyncio
async def test_user_lookup_sends_the_internal_key(sent, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "shared-key")
    user_id = await migration_service.fetch_user_id_for_email("a@example.com")
    assert user_id == "5f0000000000000000000000"
    url = sent.call_args.args[0]
    assert url == f"{settings.AUTH_SERVER_URL}/users"
    assert sent.call_args.kwargs["headers"] == {"X-Internal-Key": "shared-key"}


@pytest.mark.asyncio
async def test_no_key_header_while_unset(sent, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "")
    await migration_service.fetch_user_id_for_email("a@example.com")
    assert sent.call_args.kwargs["headers"] == {}


def test_startup_logs_an_error_while_unset(monkeypatch):
    error = mock.Mock()
    monkeypatch.setattr(migration_service.logger, "error", error)
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "")
    assert migration_service.log_if_internal_key_missing() is False
    assert "AUTH_INTERNAL_NOTIFY_KEY is not set" in error.call_args.args[0]
    monkeypatch.setattr(settings, "AUTH_INTERNAL_NOTIFY_KEY", "shared-key")
    assert migration_service.log_if_internal_key_missing() is True
