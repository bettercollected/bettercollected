"""Platform events go to the operator's event webhook only, with the event
type and the user id: no email address or other personal data leaves."""

import inspect
import json

import httpx
import pytest

from backend.app.models.dtos.event_dto import UserEventType
from backend.app.services import event_service
from backend.app.services.event_service import EventService


@pytest.fixture
def webhook(monkeypatch):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    monkeypatch.setattr(EventService, "transport", httpx.MockTransport(handler))
    hook = event_service.settings.event_webhook_settings
    monkeypatch.setattr(hook, "enabled", True)
    monkeypatch.setattr(hook, "url", "https://hooks.example.test/events")
    return requests


def test_send_event_takes_no_email():
    params = inspect.signature(EventService.send_event).parameters
    assert list(params) == ["self", "event_type", "user_id"]
    assert list(inspect.signature(EventService.post_event).parameters) == [
        "self",
        "event_type",
        "user_id",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", list(UserEventType), ids=lambda e: e.value)
async def test_the_webhook_gets_the_event_and_user_id_only(webhook, event_type):
    await EventService().post_event(event_type, "user-1")

    (request,) = webhook
    assert request.method == "POST"
    assert str(request.url) == "https://hooks.example.test/events"
    body = json.loads(request.content)
    fields = {f["name"]: f["value"] for f in body["embeds"][0]["fields"]}
    assert fields == {"Event Type": event_type.value, "": "", "User Id": "user-1"}
    assert "@" not in request.content.decode()


@pytest.mark.asyncio
async def test_an_object_id_user_id_is_sent_as_text(webhook):
    from beanie import PydanticObjectId

    user_id = PydanticObjectId()
    await EventService().post_event(UserEventType.USER_CREATED, user_id)

    (request,) = webhook
    fields = json.loads(request.content)["embeds"][0]["fields"]
    assert fields[-1]["value"] == str(user_id)


@pytest.mark.asyncio
async def test_nothing_is_sent_while_the_webhook_is_off(webhook, monkeypatch):
    monkeypatch.setattr(event_service.settings.event_webhook_settings, "enabled", False)
    await EventService().post_event(UserEventType.USER_CREATED, "user-1")
    assert webhook == []


@pytest.mark.asyncio
async def test_a_failed_post_is_logged_with_the_user_id_only(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(EventService, "transport", httpx.MockTransport(handler))
    hook = event_service.settings.event_webhook_settings
    monkeypatch.setattr(hook, "enabled", True)
    monkeypatch.setattr(hook, "url", "https://hooks.example.test/events")
    messages = []
    monkeypatch.setattr(
        event_service.loguru.logger, "warning", lambda m, *a, **k: messages.append(m)
    )

    await EventService().post_event(UserEventType.USER_CREATED, "user-1")

    assert len(messages) == 1 and "user-1" in messages[0]
