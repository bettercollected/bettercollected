import pytest

from backend.app.models.dtos.brevo_event_dto import UserEventType
from backend.app.services import brevo_service
from backend.app.services.brevo_service import BrevoService


@pytest.fixture
def tracked(monkeypatch):
    calls = []

    async def fake_track_event(self, email, event_type):
        calls.append((email, event_type))

    monkeypatch.setattr(BrevoService, "track_event", fake_track_event)
    monkeypatch.setattr(
        brevo_service.settings.event_webhook_settings, "enabled", False
    )
    return calls


@pytest.mark.asyncio
async def test_account_deleted_does_not_send_the_email_to_brevo(tracked):
    await BrevoService().send_brevo_event(
        UserEventType.ACCOUNT_DELETED, "user-1", "gone@example.com"
    )

    assert tracked == []


@pytest.mark.asyncio
async def test_other_events_are_tracked(tracked):
    await BrevoService().send_brevo_event(
        UserEventType.USER_CREATED, "user-1", "new@example.com"
    )

    assert tracked == [("new@example.com", UserEventType.USER_CREATED)]


@pytest.mark.asyncio
async def test_a_failed_send_does_not_log_the_email(monkeypatch):
    async def failing_track_event(self, email, event_type):
        raise RuntimeError("down")

    monkeypatch.setattr(BrevoService, "track_event", failing_track_event)
    monkeypatch.setattr(
        brevo_service.settings.event_webhook_settings, "enabled", False
    )
    messages = []
    monkeypatch.setattr(
        brevo_service.loguru.logger, "warning", lambda m, *a, **k: messages.append(m)
    )

    await BrevoService().send_brevo_event(
        UserEventType.USER_CREATED, "user-1", "new@example.com"
    )

    assert messages
    assert all("new@example.com" not in m for m in messages)
