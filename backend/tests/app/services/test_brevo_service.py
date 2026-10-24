import httpx
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
    monkeypatch.setattr(brevo_service.settings.event_webhook_settings, "enabled", False)
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
    monkeypatch.setattr(brevo_service.settings.event_webhook_settings, "enabled", False)
    messages = []
    monkeypatch.setattr(
        brevo_service.loguru.logger, "warning", lambda m, *a, **k: messages.append(m)
    )

    await BrevoService().send_brevo_event(
        UserEventType.USER_CREATED, "user-1", "new@example.com"
    )

    assert messages
    assert all("new@example.com" not in m for m in messages)


# -- erasing a deleted account's contact (never reaches Brevo: a mock transport)
@pytest.fixture
def brevo_api(monkeypatch):
    requests = []
    status = {"code": 204}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status["code"])

    monkeypatch.setattr(
        BrevoService, "contacts_transport", httpx.MockTransport(handler)
    )
    monkeypatch.setattr(
        brevo_service.settings.brevo_settings, "contacts_api_key", "contacts-key"
    )
    messages = []
    for level in ("info", "warning"):
        monkeypatch.setattr(
            brevo_service.loguru.logger,
            level,
            lambda m, *a, **k: messages.append(m),
        )
    return requests, status, messages


@pytest.mark.asyncio
async def test_the_contact_is_deleted_with_the_contacts_key(brevo_api):
    requests, _, messages = brevo_api
    outcome = await BrevoService().delete_contact(" Gone+x@Example.com ", "user-1")

    assert outcome == "deleted"
    (request,) = requests
    assert request.method == "DELETE"
    assert request.url.host == "api.brevo.com"
    assert request.url.raw_path.decode().startswith(
        "/v3/contacts/gone%2Bx%40example.com"
    )
    assert request.url.params["identifierType"] == "email_id"
    assert request.headers["api-key"] == "contacts-key"
    assert "ma-key" not in request.headers  # never the tracker key
    assert messages and all("example.com" not in m for m in messages)
    assert any("user-1" in m for m in messages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,outcome", [(404, "absent"), (500, "failed"), (401, "failed")]
)
async def test_brevo_answers(brevo_api, code, outcome):
    _, status, messages = brevo_api
    status["code"] = code
    assert await BrevoService().delete_contact("gone@example.com", "user-1") == outcome
    assert all("gone@example.com" not in m for m in messages)


@pytest.mark.asyncio
async def test_without_the_contacts_key_nothing_is_sent(brevo_api, monkeypatch):
    requests, _, messages = brevo_api
    monkeypatch.setattr(brevo_service.settings.brevo_settings, "contacts_api_key", "")
    assert await BrevoService().delete_contact("gone@example.com", "user-1") == (
        "skipped"
    )
    assert requests == []
    assert any("skipped" in m and "user-1" in m for m in messages)


@pytest.mark.asyncio
async def test_an_unreachable_brevo_fails_quietly(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(
        BrevoService, "contacts_transport", httpx.MockTransport(handler)
    )
    monkeypatch.setattr(
        brevo_service.settings.brevo_settings, "contacts_api_key", "contacts-key"
    )
    assert await BrevoService().delete_contact("gone@example.com", "u") == "failed"


@pytest.mark.asyncio
async def test_the_deletion_job_erases_the_contact_last(monkeypatch):
    from unittest.mock import AsyncMock

    from backend.app.container import container
    from backend.app.services import auth_service as auth_module
    from tests.app.controllers.data import testUser

    service = container.auth_service()
    order = []

    def step(name):
        async def run(*args, **kwargs):
            order.append(name)

        return run

    for name in ("delete_credentials_from_integrations", "delete_user_form_auth"):
        monkeypatch.setattr(service, name, step(name))
    workspaces = service.workspace_service
    monkeypatch.setattr(
        workspaces, "refuse_deleting_billing_owner_of_shared_workspaces", AsyncMock()
    )
    monkeypatch.setattr(workspaces, "delete_workspaces_of_user_with_forms", AsyncMock())
    erased = []

    async def delete_contact(email, user_id):
        order.append("brevo")
        erased.append((email, user_id))
        raise RuntimeError("never fails the deletion")

    monkeypatch.setattr(
        auth_module.event_logger_service, "delete_contact", delete_contact
    )
    await service.delete_user(user=testUser)

    assert order[-1] == "brevo"
    assert erased == [(testUser.sub, str(testUser.id))]
