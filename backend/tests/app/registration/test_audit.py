"""The workspace audit log's case-system events: a service created, changed or
deleted, and a form's registration switched on, changed or switched off.

Each is written with the right kind and ids (the service, the form) and, for a
change, the *names* of the parts that changed: never an address, a URL, a
secret, a name or a mapping. A change that decides where answers go, or that
removes a stored secret, is written first and refused (503 ``audit_unavailable``,
nothing changed) when the entry cannot be stored; creating a service, saving a
switched-off form and switching a form off are best effort. Everything here is
synthetic."""

import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_audit_event import (
    FORM_REGISTRATION_CHANGED,
    FORM_REGISTRATION_DISABLED,
    FORM_REGISTRATION_ENABLED,
    REGISTRATION_SERVICE_CREATED,
    REGISTRATION_SERVICE_DELETED,
    REGISTRATION_SERVICE_UPDATED,
)
from backend.app.services.registration import client
from backend.app.services.registration.service import ServiceUpdateDto
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import audit_events, fail_audit
from tests.app.registration.helpers import configure, make_service, publish
from tests.app.registration.tls_server import PUBLIC_ADDRESS

pytestmark = pytest.mark.asyncio

EVENTS = (
    REGISTRATION_SERVICE_CREATED,
    REGISTRATION_SERVICE_UPDATED,
    REGISTRATION_SERVICE_DELETED,
    FORM_REGISTRATION_ENABLED,
    FORM_REGISTRATION_CHANGED,
    FORM_REGISTRATION_DISABLED,
)
SECRET = "s3cret-value"


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(settings.registration, "REGISTRATION", "on")

    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(client, "resolve", resolve)


def service():
    return container.registration_service()


def clean(events):
    """No URL, address, secret, name or mapping in any value of any row."""
    text = " ".join(
        str(value).lower()
        for e in events
        for value in e.model_dump(mode="json", exclude_none=True, exclude={"event"}).values()
    )
    for forbidden in (
        "http",
        "case.example",
        "example org",
        "case system",
        SECRET,
        "authorization",
        "intake",
        "@",
    ):
        assert forbidden not in text, forbidden


async def refused_unrecorded(awaitable):
    with pytest.raises(HTTPException) as raised:
        await awaitable
    assert raised.value.status_code == 503
    assert raised.value.content["code"] == "audit_unavailable"


# -- the service -------------------------------------------------------------------
async def test_creating_a_service_records_its_id_best_effort(workspace, monkeypatch):
    with monkeypatch.context() as patched:
        fail_audit(patched)
        # inert until a form uses it: the store being down does not block it
        await make_service(workspace, name="Down")
    assert await audit_events(workspace, REGISTRATION_SERVICE_CREATED) == []

    created = await make_service(workspace)
    (entry,) = await audit_events(workspace, REGISTRATION_SERVICE_CREATED)
    assert (entry.user_id, entry.service_id) == (testUser.id, created.id)
    clean([entry])


async def test_changing_a_service_records_the_parts_not_their_values(workspace, monkeypatch):
    created = await make_service(workspace)

    await service().update_service(
        workspace.id,
        created.id,
        ServiceUpdateDto(
            base_url="https://other.example.org/api/", secret="Token another-secret"
        ),
        testUser,
    )
    await service().update_service(
        workspace.id, created.id, ServiceUpdateDto(name="Renamed system"), testUser
    )
    # nothing changed, nothing recorded
    await service().update_service(
        workspace.id, created.id, ServiceUpdateDto(name="Renamed system"), testUser
    )

    first, second = await audit_events(workspace, REGISTRATION_SERVICE_UPDATED)
    assert (first.service_id, sorted(first.changed)) == (created.id, ["base_url", "secret"])
    assert (second.service_id, second.changed) == (created.id, ["name"])
    clean([first, second])
    assert "another-secret" not in str([first, second]) and "other.example" not in str(
        [first, second]
    )


async def test_a_service_change_that_cannot_be_recorded_is_refused_and_not_made(
    workspace, monkeypatch
):
    created = await make_service(workspace)
    fail_audit(monkeypatch)

    await refused_unrecorded(
        service().update_service(
            workspace.id,
            created.id,
            ServiceUpdateDto(base_url="https://other.example.org/api/", secret="Token x"),
            testUser,
        )
    )
    row = await container.registration_service_repo().get(workspace.id, created.id)
    assert "other.example" not in row.base_url and "case.example.org" in row.base_url


async def test_deleting_an_unused_service_is_recorded_after_and_never_blocked(
    workspace, monkeypatch
):
    # no form uses it (that is refused), so nothing is sent through it
    gone = await make_service(workspace, name="Down")
    with monkeypatch.context() as patched:
        fail_audit(patched)
        await service().delete_service(workspace.id, gone.id, testUser)
    assert await container.registration_service_repo().get(workspace.id, gone.id) is None
    assert await audit_events(workspace, REGISTRATION_SERVICE_DELETED) == []

    created = await make_service(workspace)
    await service().delete_service(workspace.id, created.id, testUser)
    (entry,) = await audit_events(workspace, REGISTRATION_SERVICE_DELETED)
    assert entry.service_id == created.id
    clean([entry])


# -- a form's registration ---------------------------------------------------------
async def test_switching_a_form_on_is_recorded_first_and_off_is_best_effort(
    workspace, monkeypatch
):
    form = await publish(workspace)
    case_service = await make_service(workspace)

    with monkeypatch.context() as patched:
        fail_audit(patched)
        await refused_unrecorded(configure(workspace, form, case_service, ["name"]))
    assert await container.form_registration_repo().get_for_form(workspace.id, form.form_id) is None

    await configure(workspace, form, case_service, ["name"])
    (entry,) = await audit_events(workspace, FORM_REGISTRATION_ENABLED)
    assert (entry.user_id, entry.form_id, entry.service_id) == (
        testUser.id,
        form.form_id,
        case_service.id,
    )
    # the same configuration again changes nothing and records nothing
    await configure(workspace, form, case_service, ["name"])
    assert await audit_events(workspace, FORM_REGISTRATION_CHANGED) == []
    assert len(await audit_events(workspace, FORM_REGISTRATION_ENABLED)) == 1

    with monkeypatch.context() as patched:
        fail_audit(patched)
        # stopping what is sent is never blocked
        await configure(workspace, form, case_service, ["name"], enabled=False)
    stored = await container.form_registration_repo().get_for_form(workspace.id, form.form_id)
    assert not stored.enabled
    assert await audit_events(workspace, FORM_REGISTRATION_DISABLED) == []

    await configure(workspace, form, case_service, ["name"])
    await configure(workspace, form, case_service, ["name"], enabled=False)
    (off,) = await audit_events(workspace, FORM_REGISTRATION_DISABLED)
    assert (off.form_id, off.service_id) == (form.form_id, case_service.id)

    # switching off while naming no service records the one that was turned off
    other = await make_service(workspace, name="Other system")
    await configure(workspace, form, other, ["name"])
    await configure(workspace, form, None, ["name"], enabled=False)
    last = (await audit_events(workspace, FORM_REGISTRATION_DISABLED))[-1]
    assert last.service_id == other.id
    clean(await audit_events(workspace, *EVENTS))


async def test_changing_what_is_sent_names_the_parts_and_is_refused_unrecorded(
    workspace, monkeypatch
):
    form = await publish(workspace)
    case_service = await make_service(workspace)
    await configure(workspace, form, case_service, ["name"])

    with monkeypatch.context() as patched:
        fail_audit(patched)
        await refused_unrecorded(
            configure(workspace, form, case_service, ["name", "age"], path="elsewhere")
        )
    stored = await container.form_registration_repo().get_for_form(workspace.id, form.form_id)
    assert stored.path == "intake" and len(stored.variables) == 1

    await configure(workspace, form, case_service, ["name", "age"], path="elsewhere")
    (entry,) = await audit_events(workspace, FORM_REGISTRATION_CHANGED)
    assert (entry.form_id, entry.service_id) == (form.form_id, case_service.id)
    assert sorted(entry.changed) == ["path", "variables"]
    clean([entry])
    assert "elsewhere" not in str(entry)


async def test_saving_a_switched_off_form_is_best_effort(workspace, monkeypatch):
    form = await publish(workspace)
    case_service = await make_service(workspace)

    with monkeypatch.context() as patched:
        fail_audit(patched)
        await configure(workspace, form, case_service, ["name"], enabled=False)
    assert await audit_events(workspace, FORM_REGISTRATION_CHANGED) == []

    await configure(workspace, form, case_service, ["name", "age"], enabled=False)
    (entry,) = await audit_events(workspace, FORM_REGISTRATION_CHANGED)
    assert entry.changed == ["variables"]
