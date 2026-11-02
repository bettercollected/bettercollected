"""The workspace audit log's email-action events: an action created, changed,
switched on or off, or deleted.

Each is written with the right kind and ids (the form, the action) and, for a
change, the *names* of the parts that changed: never an address, a template, a
field or a name. A change that decides where answers are sent is written first
and refused (503 ``audit_unavailable``, nothing changed) when the entry cannot
be stored; switching an action off is best effort. Everything here is
synthetic."""

import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_audit_event import (
    EMAIL_ACTION_CREATED,
    EMAIL_ACTION_DELETED,
    EMAIL_ACTION_DISABLED,
    EMAIL_ACTION_ENABLED,
    EMAIL_ACTION_UPDATED,
)
from backend.app.services.email_actions.service import (
    EmailActionUpdateDto,
    TemplateDto,
)
from tests.app.controllers.data import testUser
from tests.app.email_actions.helpers import OWNER, make_action
from tests.app.form_access.helpers import audit_events, fail_audit
from tests.app.registration.helpers import publish

pytestmark = pytest.mark.asyncio

EVENTS = (
    EMAIL_ACTION_CREATED,
    EMAIL_ACTION_UPDATED,
    EMAIL_ACTION_ENABLED,
    EMAIL_ACTION_DISABLED,
    EMAIL_ACTION_DELETED,
)


@pytest.fixture(autouse=True)
def switched_on(emails_on, transport, memory_jobs):
    pass


def service():
    return container.email_action_service()


def clean(events):
    """No address, template text, field or name in any value of any row."""
    text = " ".join(
        str(value).lower()
        for e in events
        for value in e.model_dump(mode="json", exclude_none=True, exclude={"event"}).values()
    )
    for forbidden in ("@", "http", OWNER, "notify the team", "response to", "name", "age"):
        assert forbidden not in text, forbidden


async def refused_unrecorded(awaitable):
    with pytest.raises(HTTPException) as raised:
        await awaitable
    assert raised.value.status_code == 503
    assert raised.value.content["code"] == "audit_unavailable"


async def stored(workspace, form):
    return await container.form_email_action_repo().list_for_form(
        workspace.id, form.form_id
    )


async def test_creating_an_action_records_its_id_and_whether_it_is_on_never_its_content(
    workspace,
):
    form = await publish(workspace)
    created = await make_action(workspace, form, enabled=True)

    (entry,) = await audit_events(workspace, EMAIL_ACTION_CREATED)
    assert (entry.user_id, entry.form_id, entry.action_id, entry.enabled) == (
        testUser.id,
        form.form_id,
        created.id,
        True,
    )
    clean([entry])


async def test_an_action_that_cannot_be_recorded_is_not_created(workspace, monkeypatch):
    form = await publish(workspace)
    fail_audit(monkeypatch)
    await refused_unrecorded(make_action(workspace, form))
    assert await stored(workspace, form) == []


async def test_a_change_records_which_parts_changed_and_nothing_of_them(workspace):
    form = await publish(workspace)
    created = await make_action(workspace, form, enabled=False)

    await service().update_action(
        workspace.id,
        form.form_id,
        created.id,
        EmailActionUpdateDto(
            name="Another name",
            en=TemplateDto(subject="Hello {{name}}", body="Hi {{name}}\n{{answers}}"),
            respondent_copy=False,
        ),
        testUser,
    )

    (entry,) = await audit_events(workspace, EMAIL_ACTION_UPDATED)
    assert (entry.form_id, entry.action_id) == (form.form_id, created.id)
    assert sorted(entry.changed) == ["en", "name"]
    text = str(entry.model_dump(mode="json"))
    assert "Another name" not in text and "Hello" not in text and "@" not in text
    # nothing changed: nothing recorded
    await service().update_action(
        workspace.id,
        form.form_id,
        created.id,
        EmailActionUpdateDto(name="Another name"),
        testUser,
    )
    assert len(await audit_events(workspace, EMAIL_ACTION_UPDATED)) == 1


async def test_a_change_that_cannot_be_recorded_is_refused_and_not_made(
    workspace, monkeypatch
):
    form = await publish(workspace)
    created = await make_action(workspace, form)
    fail_audit(monkeypatch)

    await refused_unrecorded(
        service().update_action(
            workspace.id,
            form.form_id,
            created.id,
            EmailActionUpdateDto(name="Another name"),
            testUser,
        )
    )
    (row,) = await stored(workspace, form)
    assert row.name == "Notify the team"


async def test_switching_on_is_recorded_first_and_off_is_best_effort(
    workspace, monkeypatch
):
    form = await publish(workspace)
    created = await make_action(workspace, form, enabled=False)
    on = EmailActionUpdateDto(enabled=True)
    off = EmailActionUpdateDto(enabled=False)

    with monkeypatch.context() as patched:
        fail_audit(patched)
        await refused_unrecorded(
            service().update_action(workspace.id, form.form_id, created.id, on, testUser)
        )
    assert not (await stored(workspace, form))[0].enabled

    await service().update_action(workspace.id, form.form_id, created.id, on, testUser)
    (entry,) = await audit_events(workspace, EMAIL_ACTION_ENABLED)
    assert (entry.form_id, entry.action_id, entry.changed) == (form.form_id, created.id, None)
    # switching on is not also a change of content
    assert await audit_events(workspace, EMAIL_ACTION_UPDATED) == []

    with monkeypatch.context() as patched:
        fail_audit(patched)
        # closing it is never blocked
        await service().update_action(workspace.id, form.form_id, created.id, off, testUser)
    assert not (await stored(workspace, form))[0].enabled
    assert await audit_events(workspace, EMAIL_ACTION_DISABLED) == []

    await service().update_action(workspace.id, form.form_id, created.id, on, testUser)
    await service().update_action(workspace.id, form.form_id, created.id, off, testUser)
    (disabled,) = await audit_events(workspace, EMAIL_ACTION_DISABLED)
    assert (disabled.form_id, disabled.action_id) == (form.form_id, created.id)
    clean(await audit_events(workspace, *EVENTS))


async def test_deleting_is_recorded_first_and_refused_unrecorded(workspace, monkeypatch):
    form = await publish(workspace)
    created = await make_action(workspace, form)

    with monkeypatch.context() as patched:
        fail_audit(patched)
        await refused_unrecorded(
            service().delete_action(workspace.id, form.form_id, created.id, testUser)
        )
    assert len(await stored(workspace, form)) == 1

    await service().delete_action(workspace.id, form.form_id, created.id, testUser)
    (entry,) = await audit_events(workspace, EMAIL_ACTION_DELETED)
    assert (entry.form_id, entry.action_id) == (form.form_id, created.id)
    assert await stored(workspace, form) == []
    clean([entry])
