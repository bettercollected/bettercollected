"""The history of a response: who may read it, what it shows, that previous
values are sealed, and that it is erased with the response."""

import json

import pytest
from sqlalchemy import text as sql

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.response_revision import DELETED_ACTOR
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1
from tests.app.response_revisions.helpers import (
    RESPONDENT,
    answers_url,
    cookies,
    make_member,
    number,
    published_form,
    respondent_edit,
    revision_rows,
    revisions_url,
    stored_answers,
    submit,
    text,
)
from tests.app.controllers.test_permission_matrix import (
    editor_user,
    privacy_user,
    reviewer_user,
    viewer_user,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def edited(workspace, client):
    """A response edited once by the respondent and once by the owner."""
    form = await published_form(workspace)
    response = await submit(
        workspace, form, {"name": text("Ada"), "age": number(36), "city": text("Leiden")}
    )
    await respondent_edit(workspace, form, response, {"city": text("Utrecht")})
    done = await client.patch(
        answers_url(workspace, form, response),
        json={"answers": {"city": text("Delft"), "age": number(37)}},
        cookies=cookies(testUser),
    )
    assert done.status_code == 200, done.text
    return workspace, form, response


async def members(workspace):
    for user, roles in (
        (editor_user, [WorkspaceRoles.EDITOR]),
        (reviewer_user, [WorkspaceRoles.REVIEWER]),
        (viewer_user, [WorkspaceRoles.VIEWER]),
        (privacy_user, [WorkspaceRoles.PRIVACY_OFFICER]),
    ):
        await make_member(workspace, user, roles)


class TestListAndValues:
    async def test_lists_who_when_and_which_questions_without_values(
        self, client, edited
    ):
        listing = await client.get(revisions_url(*edited), cookies=cookies(testUser))
        assert listing.status_code == 200, listing.text
        entries = listing.json()["revisions"]
        assert [e["seq"] for e in entries] == [1, 2]
        assert entries[0]["actor"] == {"kind": "respondent", "former": False}
        assert entries[1]["actor"]["kind"] == "staff"
        assert entries[1]["actor"]["role"] == "OWNER"
        assert [c["id"] for c in entries[1]["changed"]] == ["age", "city"]
        assert [c["title"] for c in entries[1]["changed"]] == ["Age", "City"]
        assert all(e["at"] for e in entries)
        # no value, no user id, no address
        for secret in ("Leiden", "Utrecht", "Delft", str(testUser.id), testUser.sub):
            assert secret not in listing.text

    async def test_the_values_of_one_entry_come_on_demand(self, client, edited):
        first = await client.get(
            revisions_url(*edited, seq=1), cookies=cookies(testUser)
        )
        assert first.status_code == 200, first.text
        assert first.json() == {
            "seq": 1,
            "values": {"city": {"type": "text", "text": "Leiden"}},
        }
        second = await client.get(
            revisions_url(*edited, seq=2), cookies=cookies(testUser)
        )
        assert second.json()["values"]["city"]["text"] == "Utrecht"
        assert second.json()["values"]["age"]["number"] == 36

    async def test_an_unknown_entry_is_404(self, client, edited):
        assert (
            await client.get(revisions_url(*edited, seq=9), cookies=cookies(testUser))
        ).status_code == 404

    async def test_another_workspaces_member_gets_404_not_the_history(
        self, client, edited, workspace_1
    ):
        workspace, form, response = edited
        other = await client.get(
            revisions_url(workspace_1, form, response), cookies=cookies(testUser1)
        )
        assert other.status_code == 404

    async def test_a_file_link_never_comes_back(self, client, workspace):
        from backend.app.services.response_revisions.service import without_links

        cleaned = without_links(
            {
                "type": "file_upload",
                "file_metadata": {"id": "f1", "name": "cv.pdf", "url": "https://s3/x?sig=1"},
                "file_url": "https://s3/y",
                "signature": {"method": "drawn", "file_id": "img-1"},
            }
        )
        assert "url" not in cleaned["file_metadata"] and "file_url" not in cleaned
        assert "file_id" not in cleaned["signature"] and cleaned["file_metadata"]["name"] == "cv.pdf"


class TestWhoMayRead:
    async def test_the_roles_that_read_answers_read_the_history(
        self, client, edited
    ):
        workspace, form, response = edited
        await members(workspace)
        for user, expected in (
            (testUser, 200),
            (editor_user, 200),
            (reviewer_user, 200),
            (viewer_user, 200),
            (privacy_user, 403),
            (testUser1, 403),
        ):
            for url in (revisions_url(workspace, form, response), revisions_url(workspace, form, response, 1)):
                got = await client.get(url, cookies=cookies(user))
                assert got.status_code == expected, (user.sub, got.status_code, got.text)

    async def test_only_editors_and_up_edit(self, client, edited):
        workspace, form, response = edited
        await members(workspace)
        for user, expected in (
            (testUser, 200),
            (editor_user, 200),
            (reviewer_user, 403),
            (viewer_user, 403),
            (privacy_user, 403),
            (testUser1, 403),
        ):
            got = await client.patch(
                answers_url(workspace, form, response),
                json={"answers": {"note": text(f"by {user.sub}")}},
                cookies=cookies(user),
            )
            assert got.status_code == expected, (user.sub, got.status_code, got.text)
        # the refused ones changed nothing
        entries = await revision_rows(response)
        assert len([e for e in entries if e.actor_kind.value == "staff"]) == 3

    async def test_the_role_recorded_is_the_one_held_then(self, client, edited):
        workspace, form, response = edited
        await members(workspace)
        await client.patch(
            answers_url(workspace, form, response),
            json={"answers": {"note": text("x")}},
            cookies=cookies(editor_user),
        )
        entries = await revision_rows(response)
        assert entries[-1].actor_role == "EDITOR" and entries[-1].actor_id == str(editor_user.id)
        # the list names the member's role, not the id
        listing = await client.get(revisions_url(workspace, form, response), cookies=cookies(testUser))
        assert listing.json()["revisions"][-1]["actor"]["role"] == "EDITOR"
        assert str(editor_user.id) not in listing.text


class TestSealed:
    async def test_the_previous_values_are_not_stored_in_the_clear(self, edited):
        workspace, form, response = edited
        stored = await container.form_response_repo().get_response(response.response_id)
        async with container.pg_sessionmaker()() as session:
            raw = (
                await session.execute(
                    sql(
                        "select doc::text from app.response_revisions where response_pk = :pk"
                    ),
                    {"pk": str(stored.id)},
                )
            ).scalars().all()
        assert len(raw) == 2
        for doc in raw:
            for plain in ("Leiden", "Utrecht", "Delft"):
                assert plain not in doc
            assert "previous_values" in doc
        # sealed like the answers: only the keyset of this workspace and form opens it
        [entry, *_] = await revision_rows(response)
        from common.services.crypto_service import UnreadableCiphertext, crypto_service

        with pytest.raises(UnreadableCiphertext):
            crypto_service.decrypt(
                workspace_id="6" * 24, form_id=str(form.form_id), data=bytes(entry.previous_values)
            )

    async def test_an_entry_that_cannot_be_read_says_so_and_the_list_still_works(
        self, client, edited, monkeypatch
    ):
        from common.services import crypto_service as module

        def broken(*args, **kwargs):
            raise module.UnreadableCiphertext("no")

        with monkeypatch.context() as patch:
            patch.setattr(module.crypto_service, "decrypt", broken)
            got = await client.get(revisions_url(*edited, seq=1), cookies=cookies(testUser))
            assert got.status_code == 409
        assert (await client.get(revisions_url(*edited), cookies=cookies(testUser))).status_code == 200


class TestNeverElsewhere:
    async def test_the_response_reads_carry_no_history(self, client, edited, workspace):
        workspace, form, response = edited
        one = await client.get(
            f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
            cookies=cookies(testUser),
        )
        assert one.status_code == 200
        assert "revision" not in one.text.lower() and "previous" not in one.text.lower()
        lst = await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/submissions",
            cookies=cookies(testUser),
        )
        assert "previous_values" not in lst.text and "revision" not in lst.text.lower()
        # nor the respondent's own view of the submission
        mine = await client.get(
            f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}",
            cookies=cookies(RESPONDENT),
        )
        assert "previous_values" not in mine.text and "revision" not in mine.text.lower()


class TestErasure:
    async def _count(self, response_pk) -> int:
        async with container.pg_sessionmaker()() as session:
            return (
                await session.execute(
                    sql("select count(*) from app.response_revisions where response_pk = :pk"),
                    {"pk": str(response_pk)},
                )
            ).scalar_one()

    async def _pk(self, response):
        return (await container.form_response_repo().get_response(response.response_id)).id

    async def test_deleting_the_response_deletes_its_history(self, edited):
        workspace, form, response = edited
        pk = await self._pk(response)
        assert await self._count(pk) == 2
        await container.form_response_service().delete_form_response(
            form_id=form.form_id, response_id=response.response_id, workspace_id=workspace.id
        )
        assert await self._count(pk) == 0

    async def test_deleting_the_forms_responses_deletes_the_history(self, edited):
        workspace, form, response = edited
        pk = await self._pk(response)
        await container.form_response_repo().delete_by_form_id(str(form.form_id))
        assert await self._count(pk) == 0

    async def test_deleting_several_forms_responses_deletes_the_history(self, edited):
        workspace, form, response = edited
        pk = await self._pk(response)
        await container.form_response_repo().delete_by_form_ids([str(form.form_id)])
        assert await self._count(pk) == 0

    async def test_deleting_a_scope_deletes_the_history(self, edited):
        workspace, form, response = edited
        pk = await self._pk(response)
        scope = await container.form_response_service().scope(workspace.id, [str(form.form_id)])
        await container.form_response_repo().delete_in_scope(scope)
        assert await self._count(pk) == 0

    async def test_deleting_by_response_id_deletes_the_history(self, edited):
        workspace, form, response = edited
        pk = await self._pk(response)
        await container.form_response_repo().delete_response(response.response_id)
        assert await self._count(pk) == 0

    async def test_another_responses_history_stays(self, workspace, client):
        form = await published_form(workspace)
        one = await submit(workspace, form, {"name": text("Ada")})
        two = await submit(workspace, form, {"name": text("Bo")})
        for response in (one, two):
            await respondent_edit(workspace, form, response, {"name": text("Edited")})
        await container.form_response_service().delete_form_response(
            form_id=form.form_id, response_id=one.response_id, workspace_id=workspace.id
        )
        assert len(await revision_rows(two)) == 1

    async def test_with_the_switch_off_the_history_is_still_erased(
        self, edited, monkeypatch
    ):
        workspace, form, response = edited
        pk = await self._pk(response)
        monkeypatch.setattr(settings, "RESPONSE_REVISIONS_ENABLED", False)
        await container.form_response_repo().delete_response(response.response_id)
        assert await self._count(pk) == 0


class TestAccountDeletion:
    async def test_a_deleted_staff_account_leaves_the_entry_without_the_id(
        self, client, edited
    ):
        workspace, form, response = edited
        assert await container.response_revision_repo().forget_actor(testUser.id) == 1
        entries = await revision_rows(response)
        staff = [e for e in entries if e.actor_kind.value == "staff"]
        assert staff[0].actor_id == DELETED_ACTOR and staff[0].actor_role == "OWNER"
        # what changed and when stay; the respondent's entry is untouched
        assert staff[0].changed == ["age", "city"]
        listing = await client.get(revisions_url(*edited), cookies=cookies(testUser))
        actor = listing.json()["revisions"][1]["actor"]
        assert actor["former"] is True and actor["role"] == "OWNER" and "name" not in actor
        # a second run finds nothing more
        assert await container.response_revision_repo().forget_actor(testUser.id) == 0
