"""The workspace audit log's member and form events: a member invited, an
invitation revoked or accepted, a member removed, a role changed, a form
published or deleted, a response deleted, an export taken.

Each is written with the right kind and ids and nothing else (no name, no
address, no answer). The ones that remove data or give access are written
*before* the change and refuse it (503 ``audit_unavailable``) when the entry
cannot be stored; the rest are best effort. A statement count shows each hot
path pays for exactly one INSERT. Everything here is synthetic."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient
from sqlalchemy import event

from backend.app.container import container
from backend.app.models.invitation_request import InvitationRequest
from backend.app.schemas.workspace_audit_event import (
    FORM_DELETED,
    FORM_PUBLISHED,
    MEMBER_FORM_EVENTS,
    MEMBER_INVITATION_ACCEPTED,
    MEMBER_INVITATION_REVOKED,
    MEMBER_INVITED,
    MEMBER_REMOVED,
    MEMBER_ROLE_CHANGED,
    RESPONSE_EXPORT,
    RESPONSES_DELETED,
)
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    create_form,
    fail_audit,
)
from tests.app.response_export.helpers import answers, publish, start, submit

pytestmark = pytest.mark.asyncio

NEWCOMER = "newcomer@example.com"


@pytest.fixture()
def auth_service():
    """The auth service: its user lookup and its invitation mail. ``sent`` lists
    the mails that went out."""
    sent = []

    async def get(url, **kwargs):
        if str(url).endswith("/users/invite/send/mail"):
            sent.append(kwargs.get("params", {}).get("email"))
            return "Mail sent successfully!!"
        ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {"users_info": [{"_id": i, "email": f"{i}@example.com"} for i in ids]}

    with patch("common.services.http_client.HttpClient.get", AsyncMock(side_effect=get)):
        yield sent


@contextmanager
def audit_down():
    """The audit log cannot be written, for the length of the block."""

    async def refuse(document):
        raise RuntimeError("audit store down")

    with patch.object(container.workspace_audit_repo(), "record", refuse):
        yield


def dump(events) -> str:
    return str([e.model_dump(mode="json") for e in events])


async def invitation_of(workspace, token):
    return await container.workspace_invitation_repo().get_workspace_invitation_by_token(
        workspace.id, token
    )


async def invite(client, workspace, role="VIEWER", email=NEWCOMER, by=testUser):
    return await client.post(
        f"{api(workspace)}/members/invitations",
        json={"email": email, "role": role},
        cookies=cookies(by),
    )


# -- members ---------------------------------------------------------------------
async def test_inviting_records_the_invitation_by_id_and_role_never_the_address(
    client: AsyncClient, workspace, auth_service
):
    response = await invite(client, workspace, role="REVIEWER")
    assert response.status_code == 200, response.text
    token = response.json()["invitation_token"]
    invitation = await invitation_of(workspace, token)

    (entry,) = await audit_events(workspace, MEMBER_INVITED)
    assert (entry.user_id, entry.invitation_id, entry.role) == (
        testUser.id,
        str(invitation.id),
        "REVIEWER",
    )
    assert entry.target_user_id is None
    text = dump([entry])
    assert "@" not in text and NEWCOMER not in text and token not in text
    assert auth_service == [NEWCOMER]


async def test_an_invitation_that_cannot_be_recorded_is_not_sent(
    client: AsyncClient, workspace, auth_service, monkeypatch
):
    fail_audit(monkeypatch)
    response = await invite(client, workspace)
    assert response.status_code == 503
    assert response.json()["code"] == "audit_unavailable"
    # the mail carrying the token never went out
    assert auth_service == []


async def test_revoking_an_invitation_records_it_and_is_refused_unrecorded(
    client: AsyncClient, workspace, auth_service, monkeypatch
):
    invited = await invite(client, workspace)
    token = invited.json()["invitation_token"]
    invitation = await invitation_of(workspace, token)
    url = f"{api(workspace)}/members/invitations/{token}"

    with audit_down():
        refused = await client.delete(url, cookies=cookies(testUser))
        assert refused.status_code == 503
        assert (await invitation_of(workspace, token)).id == invitation.id

    revoked = await client.delete(url, cookies=cookies(testUser))
    assert revoked.status_code == 200, revoked.text
    (entry,) = await audit_events(workspace, MEMBER_INVITATION_REVOKED)
    assert (entry.user_id, entry.invitation_id) == (testUser.id, str(invitation.id))
    assert token not in dump([entry])


async def test_revoking_another_workspaces_token_writes_nothing(
    client: AsyncClient, workspace, workspace_1, auth_service
):
    other = await container.workspace_invitation_repo().create_workspace_invitation(
        workspace_1.id, InvitationRequest(email=NEWCOMER, role="VIEWER")
    )
    response = await client.delete(
        f"{api(workspace)}/members/invitations/{other.invitation_token}",
        cookies=cookies(testUser),
    )
    assert response.status_code == 404
    assert await audit_events(workspace, MEMBER_INVITATION_REVOKED) == []


async def test_accepting_an_invitation_is_recorded_and_never_blocks_joining(
    client: AsyncClient, workspace, auth_service, monkeypatch
):
    newcomer = User(id=str(RecordId()), sub=NEWCOMER)
    invitation = await container.workspace_invitation_repo().create_workspace_invitation(
        workspace.id,
        InvitationRequest(email=NEWCOMER, role="VIEWER"),
        invited_by=testUser.id,
    )
    with audit_down():
        accepted = await client.post(
            f"{api(workspace)}/members/invitations/{invitation.invitation_token}",
            params={"response_status": "ACCEPTED"},
            cookies=cookies(newcomer),
        )
        # the member's own act: a store that is down does not keep them out
        assert accepted.status_code == 200, accepted.text
        assert await container.workspace_user_repo().find_workspace_user(
            workspace.id, newcomer.id
        ) is not None

    second = User(id=str(RecordId()), sub="second@example.com")
    again = await container.workspace_invitation_repo().create_workspace_invitation(
        workspace.id,
        InvitationRequest(email=second.sub, role="REVIEWER"),
        invited_by=testUser.id,
    )
    accepted = await client.post(
        f"{api(workspace)}/members/invitations/{again.invitation_token}",
        params={"response_status": "ACCEPTED"},
        cookies=cookies(second),
    )
    assert accepted.status_code == 200, accepted.text
    (entry,) = await audit_events(workspace, MEMBER_INVITATION_ACCEPTED)
    assert (entry.user_id, entry.target_user_id, entry.invitation_id, entry.role) == (
        second.id,
        second.id,
        str(again.id),
        "REVIEWER",
    )
    assert "@" not in dump([entry])


async def test_declining_an_invitation_writes_no_acceptance(
    client: AsyncClient, workspace, auth_service
):
    person = User(id=str(RecordId()), sub=NEWCOMER)
    invitation = await container.workspace_invitation_repo().create_workspace_invitation(
        workspace.id,
        InvitationRequest(email=NEWCOMER, role="VIEWER"),
        invited_by=testUser.id,
    )
    declined = await client.post(
        f"{api(workspace)}/members/invitations/{invitation.invitation_token}",
        params={"response_status": "REJECTED"},
        cookies=cookies(person),
    )
    assert declined.status_code == 200, declined.text
    assert await audit_events(workspace, MEMBER_INVITATION_ACCEPTED) == []


async def test_removing_a_member_records_who_removed_whom_and_is_refused_unrecorded(
    client: AsyncClient, workspace, auth_service, monkeypatch
):
    person = await add_member(workspace, "VIEWER")
    url = f"{api(workspace)}/members/{person.id}"

    with audit_down():
        refused = await client.delete(url, cookies=cookies(testUser))
        assert refused.status_code == 503
        assert refused.json()["code"] == "audit_unavailable"
        assert await container.workspace_user_repo().find_workspace_user(
            workspace.id, person.id
        ) is not None

    removed = await client.delete(url, cookies=cookies(testUser))
    assert removed.status_code == 200, removed.text
    (entry,) = await audit_events(workspace, MEMBER_REMOVED)
    assert (entry.user_id, entry.target_user_id) == (testUser.id, person.id)
    assert "@" not in dump([entry])


async def test_a_member_removal_writes_one_removed_entry_beside_its_side_effects(
    client: AsyncClient, workspace, auth_service
):
    creator = await add_member(workspace, "COLLABORATOR")
    await create_form(workspace, creator)
    response = await client.delete(
        f"{api(workspace)}/members/{creator.id}", cookies=cookies(testUser)
    )
    assert response.status_code == 200, response.text
    assert len(await audit_events(workspace, MEMBER_REMOVED)) == 1
    assert len(await audit_events(workspace, "form_creator_reassigned")) == 1


@pytest.mark.parametrize(
    "role, previous",
    [("ADMIN", "VIEWER"), ("EDITOR", "VIEWER"), ("PRIVACY_OFFICER", "VIEWER")],
    ids=["admin", "editor", "privacy-officer"],
)
async def test_changing_a_role_records_the_new_and_the_old_role(
    client: AsyncClient, workspace, auth_service, role, previous
):
    person = await add_member(workspace, "VIEWER")
    response = await client.patch(
        f"{api(workspace)}/members/{person.id}",
        json={"role": role},
        cookies=cookies(testUser),
    )
    assert response.status_code == 200, response.text
    (entry,) = await audit_events(workspace, MEMBER_ROLE_CHANGED)
    assert (entry.user_id, entry.target_user_id, entry.role, entry.previous_role) == (
        testUser.id,
        person.id,
        role,
        previous,
    )


async def test_a_role_change_that_cannot_be_recorded_changes_nothing(
    client: AsyncClient, workspace, auth_service, monkeypatch
):
    person = await add_member(workspace, "VIEWER")
    fail_audit(monkeypatch)
    response = await client.patch(
        f"{api(workspace)}/members/{person.id}",
        json={"role": "ADMIN"},
        cookies=cookies(testUser),
    )
    assert response.status_code == 503
    membership = await container.workspace_user_repo().find_workspace_user(
        workspace.id, person.id
    )
    assert membership.roles == ["VIEWER"]


async def test_a_refused_role_change_writes_nothing(
    client: AsyncClient, workspace, auth_service
):
    # no one changes their own role
    response = await client.patch(
        f"{api(workspace)}/members/{testUser.id}",
        json={"role": "VIEWER"},
        cookies=cookies(testUser),
    )
    assert response.status_code == 403
    assert await audit_events(workspace, MEMBER_ROLE_CHANGED) == []


# -- forms and responses ----------------------------------------------------------
async def test_publishing_records_the_form_id_and_never_blocks_the_publish(
    workspace, monkeypatch
):
    first = await create_form(workspace, testUser)
    await container.workspace_form_service().publish_form(
        workspace.id, first.form_id, testUser
    )
    (entry,) = await audit_events(workspace, FORM_PUBLISHED)
    assert (entry.user_id, entry.form_id) == (testUser.id, first.form_id)

    # best effort: a store that is down never undoes or refuses a publish
    second = await create_form(workspace, testUser)
    with audit_down():
        published = await container.workspace_form_service().publish_form(
            workspace.id, second.form_id, testUser
        )
        assert published is not None
    assert [e.form_id for e in await audit_events(workspace, FORM_PUBLISHED)] == [
        first.form_id
    ]


async def test_deleting_a_form_records_it_first_and_is_refused_unrecorded(
    client: AsyncClient, workspace, monkeypatch
):
    form = await create_form(workspace, testUser)
    url = f"{api(workspace)}/forms/{form.form_id}"

    with audit_down():
        refused = await client.delete(url, cookies=cookies(testUser))
        assert refused.status_code == 503
        assert await container.workspace_form_repo().find_workspace_form(
            workspace.id, form.form_id
        ) is not None

    deleted = await client.delete(url, cookies=cookies(testUser))
    assert deleted.status_code == 200, deleted.text
    (entry,) = await audit_events(workspace, FORM_DELETED)
    assert (entry.user_id, entry.form_id) == (testUser.id, form.form_id)
    assert await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    ) is None


async def test_deleting_a_form_that_is_not_there_writes_nothing(
    client: AsyncClient, workspace
):
    response = await client.delete(
        f"{api(workspace)}/forms/{RecordId()}", cookies=cookies(testUser)
    )
    assert response.status_code == 404
    assert await audit_events(workspace, FORM_DELETED) == []


async def test_deleting_a_response_records_the_ids_and_is_refused_unrecorded(
    client: AsyncClient, workspace, monkeypatch
):
    form = await publish(workspace)
    stored = await submit(workspace, form, answers("Ada Lovelace"))
    url = f"{api(workspace)}/forms/{form.form_id}/response/{stored.response_id}"

    with audit_down():
        refused = await client.delete(url, cookies=cookies(testUser))
        assert refused.status_code == 503
        assert await container.form_response_service().workspace_response(
            workspace.id, stored.response_id
        ) is not None

    deleted = await client.delete(url, cookies=cookies(testUser))
    assert deleted.status_code == 200, deleted.text
    (entry,) = await audit_events(workspace, RESPONSES_DELETED)
    assert (entry.user_id, entry.form_id, entry.response_id, entry.count) == (
        testUser.id,
        form.form_id,
        str(stored.response_id),
        1,
    )
    # an id, never an answer
    assert "Ada" not in dump([entry])


async def test_deleting_a_response_that_is_not_there_writes_nothing(
    client: AsyncClient, workspace
):
    form = await publish(workspace)
    response = await client.delete(
        f"{api(workspace)}/forms/{form.form_id}/response/{RecordId()}",
        cookies=cookies(testUser),
    )
    assert response.status_code == 404
    assert await audit_events(workspace, RESPONSES_DELETED) == []


# -- exports ---------------------------------------------------------------------
async def test_an_export_points_at_its_own_audit_row(
    client: AsyncClient, workspace, monkeypatch
):
    form = await publish(workspace)
    await submit(workspace, form, answers("Ada Lovelace"))
    await submit(workspace, form, answers("Grace Hopper"))

    response = await start(client, workspace, form)
    assert response.status_code == 200, response.text
    (row,) = await container.response_export_repo().list_for_form(
        workspace.id, form.form_id
    )
    (entry,) = await audit_events(workspace, RESPONSE_EXPORT)
    assert (
        entry.user_id,
        entry.form_id,
        entry.export_id,
        entry.export_channel,
        entry.export_format,
        entry.count,
    ) == (testUser.id, form.form_id, str(row.id), "export", "csv", 2)
    text = dump([entry])
    assert "Ada" not in text and "Grace" not in text and "@" not in text


async def test_an_export_is_not_blocked_by_a_store_that_is_down(
    client: AsyncClient, workspace, monkeypatch
):
    """The export row (kept as long as the form) is the record and is stored
    first; the pointer is best effort."""
    form = await publish(workspace)
    await submit(workspace, form)
    fail_audit(monkeypatch)
    response = await start(client, workspace, form)
    assert response.status_code == 200, response.text
    assert len(await container.response_export_repo().list_for_form(
        workspace.id, form.form_id
    )) == 1


async def test_a_bulk_read_and_a_response_pdf_point_at_their_rows(
    client: AsyncClient, workspace
):
    form = await publish(workspace)
    stored = await submit(workspace, form)
    bulk = await client.get(
        f"{api(workspace)}/forms/{form.form_id}/all-submissions",
        cookies=cookies(testUser),
    )
    assert bulk.status_code == 200, bulk.text
    pdf = await client.get(
        f"{api(workspace)}/submissions/{stored.response_id}/pdf",
        cookies=cookies(testUser),
    )
    assert pdf.status_code == 200, pdf.text

    rows = {
        r.channel: r
        for r in await container.response_export_repo().list_for_form(
            workspace.id, form.form_id
        )
    }
    entries = {e.export_channel: e for e in await audit_events(workspace, RESPONSE_EXPORT)}
    assert set(entries) == {"all_submissions", "response_pdf"}
    assert entries["all_submissions"].export_id == str(rows["all_submissions"].id)
    assert (entries["all_submissions"].export_format, entries["all_submissions"].count) == (
        "json",
        1,
    )
    assert entries["response_pdf"].export_id == str(rows["response_pdf"].id)
    assert (entries["response_pdf"].export_format, entries["response_pdf"].count) == ("pdf", 1)


async def test_an_export_refused_before_it_starts_writes_no_pointer(
    client: AsyncClient, workspace
):
    form = await publish(workspace)
    stranger = await add_member(workspace, "VIEWER")
    response = await start(client, workspace, form, user=stranger)
    assert response.status_code == 403
    assert await audit_events(workspace, RESPONSE_EXPORT) == []


# -- the catalogue ----------------------------------------------------------------
def test_the_new_kinds_are_listed_once_and_distinct_from_the_older_ones():
    from backend.app.schemas import workspace_audit_event as schema

    assert len(set(MEMBER_FORM_EVENTS)) == len(MEMBER_FORM_EVENTS) == 9
    older = set(schema.ACCESS_EVENTS) | set(schema.TOTP_EVENTS) | set(schema.SSO_EVENTS)
    assert not older & set(MEMBER_FORM_EVENTS)


# -- one statement ----------------------------------------------------------------
@contextmanager
def counted():
    """Every statement the database receives, in order."""
    seen = []
    engine = container.pg_engine().sync_engine

    def before(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", before)


def inserts_of_audit(statements):
    return [s for s in statements if "INSERT INTO app.workspace_audit_events" in s]


async def paid_for_audit(monkeypatch, work_without, work_with):
    """The statements ``work_with`` runs beyond ``work_without``'s: the first
    runs with the audit write switched off, the second as shipped. Both do the
    same work on their own rows, so the difference is the audit alone."""
    repo = container.workspace_audit_repo()
    real = repo.record

    async def nothing(document):
        return None

    monkeypatch.setattr(repo, "record", nothing)
    with counted() as baseline:
        await work_without()
    monkeypatch.setattr(repo, "record", real)
    with counted() as shipped:
        await work_with()
    assert len(shipped) == len(baseline) + 1, (len(baseline), len(shipped))
    assert len(inserts_of_audit(shipped)) == 1
    assert inserts_of_audit(baseline) == []


async def test_publishing_pays_one_insert(workspace, monkeypatch):
    service = container.workspace_form_service()
    a = await create_form(workspace, testUser)
    b = await create_form(workspace, testUser)
    await paid_for_audit(
        monkeypatch,
        lambda: service.publish_form(workspace.id, a.form_id, testUser),
        lambda: service.publish_form(workspace.id, b.form_id, testUser),
    )


async def test_deleting_a_response_pays_one_insert(workspace, monkeypatch):
    form = await publish(workspace)
    a = await submit(workspace, form, answers("A"))
    b = await submit(workspace, form, answers("B"))
    service = container.workspace_form_service()
    await paid_for_audit(
        monkeypatch,
        lambda: service.delete_form_response(workspace.id, form.form_id, a.response_id, testUser),
        lambda: service.delete_form_response(workspace.id, form.form_id, b.response_id, testUser),
    )


async def test_deleting_a_form_pays_one_insert(workspace, monkeypatch):
    service = container.workspace_form_service()
    a = await create_form(workspace, testUser)
    b = await create_form(workspace, testUser)
    await paid_for_audit(
        monkeypatch,
        lambda: service.delete_form_from_workspace(workspace.id, a.form_id, testUser),
        lambda: service.delete_form_from_workspace(workspace.id, b.form_id, testUser),
    )


async def test_changing_a_role_pays_one_insert(workspace, auth_service, monkeypatch):
    service = container.workspace_members_service()
    a = await add_member(workspace, "VIEWER")
    b = await add_member(workspace, "VIEWER")
    from backend.app.models.enum.workspace_roles import WorkspaceRoles

    await paid_for_audit(
        monkeypatch,
        lambda: service.update_member_role(workspace.id, a.id, WorkspaceRoles.ADMIN, testUser),
        lambda: service.update_member_role(workspace.id, b.id, WorkspaceRoles.ADMIN, testUser),
    )


async def test_removing_a_member_pays_one_insert_for_its_own_entry(
    workspace, auth_service, monkeypatch
):
    service = container.workspace_members_service()
    a = await add_member(workspace, "VIEWER")
    b = await add_member(workspace, "VIEWER")
    await paid_for_audit(
        monkeypatch,
        lambda: service.delete_workspace_member(workspace.id, a.id, testUser),
        lambda: service.delete_workspace_member(workspace.id, b.id, testUser),
    )


async def test_starting_an_export_pays_one_insert(workspace, monkeypatch):
    form = await publish(workspace)
    await submit(workspace, form)
    service = container.response_export_service()

    async def stream():
        from backend.app.models.filter_queries.response_export import ResponseExportFilters

        started = await service.request(
            workspace.id, form.form_id, testUser, None, ResponseExportFilters()
        )
        # the stream is never read: give its slot back
        await service._exports.delete_by_form_ids([form.form_id])
        return started

    # the first request of a window opens the rate limit's counter: a warm-up
    # makes the two measured calls the same shape
    await stream()
    await paid_for_audit(monkeypatch, stream, stream)
