"""An API key's edit of a response it made (the submissions API) is recorded in
the revision log like any other edit while RESPONSE_REVISIONS_ENABLED is on:
actor kind ``api_key``, the key's id, no user. The three ways to edit a response
(the respondent, the key that made it, a staff member) are exclusive."""

import json

import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.repositories.postgres import responses as responses_module
from backend.app.schemas.response_revision import RevisionEditor
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.test_submissions_api import (  # noqa: F401
    BASE,
    SCOPES,
    _auth,
    _form,
    _only_response,
    _submit,
    _body,
    _switch_on,
    text,
)
from tests.app.response_revisions.helpers import cookies, revision_rows, revisions_url

pytestmark = pytest.mark.asyncio


async def make_key(workspace):
    created = await container.api_key_service().create_key(
        workspace.id,
        CreateAPIKeyDto(name="edit key", scopes=SCOPES, acknowledge_unredacted_responses=True),
        testUser,
    )
    return created.token, str(created.id)


async def made_by_a_key(client, workspace):
    form_id = await _form(client, workspace)
    token, key_id = await make_key(workspace)
    created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
    assert created.status_code == 201, created.text
    return form_id, token, key_id, created.json()["responseId"]


async def key_edit(client, token, form_id, response_id, name):
    return await client.patch(
        f"{BASE}/forms/{form_id}/submissions/{response_id}",
        json={"answers": {"name": name}},
        headers=_auth(token),
    )


class FakeForm:
    """The bits of the form-shaped objects the revision helpers read."""

    def __init__(self, form_id):
        self.form_id = form_id


async def rows_for(workspace, form_id, response_id):
    stored = await container.form_response_repo().get_response(response_id)
    return await container.response_revision_repo().list_for_response(stored.id)


class TestKeyEditIsLogged:
    async def test_an_entry_names_the_key_and_no_user(self, client, workspace):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        # (the key's own submission is not an edit: no entry yet)
        assert await rows_for(workspace, form_id, response_id) == []
        assert (await key_edit(client, token, form_id, response_id, "Ada L.")).status_code == 200
        [entry] = await rows_for(workspace, form_id, response_id)
        assert entry.actor_kind.value == "api_key"
        assert entry.actor_id == key_id
        assert entry.actor_role is None
        assert entry.seq == 1 and entry.changed == ["name"]
        assert str(testUser.id) not in json.dumps(entry.model_dump(mode="json", exclude={"previous_values"}), default=str)

    async def test_staff_read_it_without_the_key_id(self, client, workspace):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        await key_edit(client, token, form_id, response_id, "Ada L.")
        listing = await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/submissions/{response_id}/revisions",
            cookies=cookies(testUser),
        )
        assert listing.status_code == 200, listing.text
        [entry] = listing.json()["revisions"]
        assert entry["actor"] == {"kind": "api_key", "former": False}
        assert key_id not in listing.text and "Ada" not in listing.text
        values = await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/submissions/{response_id}/revisions/1",
            cookies=cookies(testUser),
        )
        assert values.json()["values"]["name"]["text"] == "Ada"

    async def test_an_edit_that_changes_nothing_writes_no_entry(self, client, workspace):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        assert (await key_edit(client, token, form_id, response_id, "Ada")).status_code == 200
        assert await rows_for(workspace, form_id, response_id) == []

    async def test_with_the_switch_off_nothing_is_recorded(
        self, client, workspace, monkeypatch
    ):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        monkeypatch.setattr(settings, "RESPONSE_REVISIONS_ENABLED", False)
        assert (await key_edit(client, token, form_id, response_id, "Ada L.")).status_code == 200
        assert await rows_for(workspace, form_id, response_id) == []

    async def test_a_key_that_edits_often_meets_the_limit_a_respondent_does_not(
        self, client, workspace, monkeypatch
    ):
        monkeypatch.setattr(responses_module, "MAX_REVISIONS", 2)
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        for value in ("a", "b"):
            assert (await key_edit(client, token, form_id, response_id, value)).status_code == 200
        with pytest.raises(HTTPException) as refused:
            await container.workspace_form_service().patch_response_as_key(
                workspace.id,
                form_id,
                response_id,
                StandardFormResponseCamelModel(answers={"name": text("c")}),
                key_id,
            )
        assert refused.value.status_code == 409
        assert refused.value.content["code"] == "revision_limit"
        # the data subject is never refused for it
        assert len(await rows_for(workspace, form_id, response_id)) == 2

    async def test_a_deleted_user_never_touches_a_keys_entries(self, client, workspace):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        await key_edit(client, token, form_id, response_id, "Ada L.")
        # an id that happens to equal the key's: only staff entries are replaced
        assert await container.response_revision_repo().forget_actor(key_id) == 0
        [entry] = await rows_for(workspace, form_id, response_id)
        assert entry.actor_id == key_id


class TestWhoMayEdit:
    async def test_another_key_cannot_edit_while_staff_edit_is_on(self, client, workspace):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        other, _ = await make_key(workspace)
        refused = await key_edit(client, other, form_id, response_id, "Hijacked")
        assert refused.status_code == 404
        assert await rows_for(workspace, form_id, response_id) == []
        from tests.app.controllers.test_submissions_api import _answers_of

        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"

    async def test_a_respondents_response_is_not_a_keys_to_edit(self, client, workspace):
        from tests.app.controllers.test_submissions_api import _answers_of

        form_id = await _form(client, workspace)
        token, _ = await make_key(workspace)
        sent = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": {"name": text("Ada")}})},
        )
        assert sent.status_code == 200
        items, _ = await _only_response(workspace, form_id)
        response_id = items[0]["responseId"]
        refused = await key_edit(client, token, form_id, response_id, "Hijacked")
        assert refused.status_code == 404
        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"
        assert await rows_for(workspace, form_id, response_id) == []

    async def test_staff_can_edit_what_a_key_made_and_it_is_their_entry(
        self, client, workspace
    ):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        staff = await client.patch(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/submissions/{response_id}/answers",
            json={"answers": {"name": text("By staff")}},
            cookies=cookies(testUser),
        )
        assert staff.status_code == 200, staff.text
        await key_edit(client, token, form_id, response_id, "By key")
        entries = await rows_for(workspace, form_id, response_id)
        assert [(e.seq, e.actor_kind.value) for e in entries] == [(1, "staff"), (2, "api_key")]
        assert entries[0].actor_id == str(testUser.id) and entries[1].actor_id == key_id

    async def test_a_respondent_cannot_edit_a_response_a_key_made(self, client, workspace):
        from tests.app.controllers.data import testUser2
        from tests.app.response_revisions.helpers import respondent_edit

        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)

        class Ref:
            pass

        ref = Ref()
        ref.response_id = response_id
        form = FakeForm(form_id)
        # (respondent editing needs the form to allow it and a signed-in owner of the response)
        association = await container.workspace_form_repo().find_workspace_form(workspace.id, form_id)
        association.settings.require_verified_identity = True
        association.settings.allow_editing_response = True
        await container.workspace_form_repo().save(association)
        with pytest.raises(HTTPException) as refused:
            await respondent_edit(workspace, form, ref, {"name": text("Hijacked")}, testUser2)
        assert refused.value.status_code == 403
        assert await rows_for(workspace, form_id, response_id) == []


class TestTheThreeAreExclusive:
    async def test_the_repository_refuses_a_staff_member_and_a_key_together(
        self, client, workspace
    ):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        stored = await container.form_response_repo().get_response(response_id)
        with pytest.raises(ValueError):
            await container.form_response_repo().patch_form_response(
                form_id=form_id,
                document_id=stored.id,
                response=StandardFormResponseCamelModel(answers={"name": text("x")}),
                workspace_id=workspace.id,
                editor=RevisionEditor(user_id=str(testUser.id), role="OWNER"),
                source_key_id=key_id,
            )
        from tests.app.controllers.test_submissions_api import _answers_of

        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"

    async def test_the_service_refuses_it_too(self, client, workspace):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        stored = await container.form_response_repo().get_response(response_id)
        with pytest.raises(ValueError):
            await container.workspace_form_service()._apply_edit(
                workspace_id=workspace.id,
                form_id=form_id,
                response_id=response_id,
                existing=stored,
                response=StandardFormResponseCamelModel(answers={"name": text("x")}),
                form=await container.form_service().get_latest_version_of_form(form_id),
                form_files=None,
                workspace_form=await container.workspace_form_repo().find_workspace_form(workspace.id, form_id),
                user=None,
                client_ip=None,
                editor=RevisionEditor(user_id=str(testUser.id)),
                source_key_id=key_id,
            )

    async def test_a_key_is_checked_under_the_lock_even_with_the_switch_on(
        self, client, workspace
    ):
        form_id, token, key_id, response_id = await made_by_a_key(client, workspace)
        stored = await container.form_response_repo().get_response(response_id)
        with pytest.raises(HTTPException) as refused:
            await container.form_response_repo().patch_form_response(
                form_id=form_id,
                document_id=stored.id,
                response=StandardFormResponseCamelModel(answers={"name": text("x")}),
                workspace_id=workspace.id,
                source_key_id="6" * 24,
                record=True,
            )
        assert refused.value.status_code == 404
        assert await rows_for(workspace, form_id, response_id) == []
