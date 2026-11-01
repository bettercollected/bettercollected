"""A staff member changes answers (``PATCH .../submissions/{id}/answers``):
the switch, the permission, validation like the respondent's own edit, and
the history entry that is written with the change."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.services.response_revisions.mode import DISABLED_CODE
from backend.config import settings
from tests.app.controllers.data import testUser1
from tests.app.response_revisions.helpers import (
    AGE,
    CITY,
    COLOUR,
    NAME,
    NOTE,
    RESPONDENT,
    answers_url,
    choice,
    cookies,
    make_member,
    number,
    published_form,
    question,
    respondent_edit,
    revision_rows,
    revisions_url,
    stored_answers,
    submit,
    text,
)
from tests.app.controllers.data import invited_user

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def case(workspace):
    form = await published_form(workspace)
    response = await submit(
        workspace,
        form,
        {"name": text("Ada"), "age": number(36), "city": text("Leiden")},
    )
    return workspace, form, response


async def edit(client: AsyncClient, case, answers, user=None):
    workspace, form, response = case
    from tests.app.controllers.data import testUser

    return await client.patch(
        answers_url(workspace, form, response),
        json={"answers": answers},
        cookies=cookies(user or testUser),
    )


class TestSwitch:
    async def test_off_a_staff_edit_is_refused_and_nothing_changes(
        self, client, case, monkeypatch
    ):
        monkeypatch.setattr(settings, "RESPONSE_REVISIONS_ENABLED", False)
        response = await edit(client, case, {"city": text("Delft")})
        assert response.status_code == 422, response.text
        assert response.json()["code"] == DISABLED_CODE
        assert (await stored_answers(case[0], case[2]))["city"]["text"] == "Leiden"

    async def test_off_the_history_is_refused_too(self, client, case, monkeypatch):
        from tests.app.controllers.data import testUser

        monkeypatch.setattr(settings, "RESPONSE_REVISIONS_ENABLED", False)
        listing = await client.get(
            revisions_url(*case), cookies=cookies(testUser)
        )
        assert listing.status_code == 422
        assert listing.json()["code"] == DISABLED_CODE

    async def test_off_a_respondents_own_edit_records_nothing(
        self, case, monkeypatch
    ):
        workspace, form, response = case
        monkeypatch.setattr(settings, "RESPONSE_REVISIONS_ENABLED", False)
        await respondent_edit(workspace, form, response, {"city": text("Utrecht")})
        assert (await stored_answers(workspace, response))["city"]["text"] == "Utrecht"
        assert await revision_rows(response) == []

    async def test_the_permissions_answer_carries_the_switch(
        self, client, workspace, monkeypatch
    ):
        from tests.app.controllers.data import testUser

        url = f"/api/v1/workspaces/{workspace.id}/permissions"
        assert (await client.get(url, cookies=cookies(testUser))).json()[
            "responseRevisionsEnabled"
        ] is True
        monkeypatch.setattr(settings, "RESPONSE_REVISIONS_ENABLED", False)
        assert (await client.get(url, cookies=cookies(testUser))).json()[
            "responseRevisionsEnabled"
        ] is False


class TestStaffEdit:
    async def test_changes_the_answer_and_writes_one_entry(self, client, case):
        workspace, form, response = case
        result = await edit(client, case, {"city": text("Delft"), "age": number(37)})
        assert result.status_code == 200, result.text
        assert result.json() == {"changed": ["age", "city"], "revision": 1}
        answers = await stored_answers(workspace, response)
        assert answers["city"]["text"] == "Delft" and answers["age"]["number"] == 37
        # what was not sent is kept
        assert answers["name"]["text"] == "Ada"
        [entry] = await revision_rows(response)
        assert entry.seq == 1 and entry.actor_kind.value == "staff"
        assert entry.actor_role == "OWNER"
        assert entry.changed == ["age", "city"]

    async def test_an_edit_that_changes_nothing_writes_nothing(self, client, case):
        workspace, form, response = case
        before = await container.form_response_repo().get_response(response.response_id)
        result = await edit(client, case, {"city": text("Leiden")})
        assert result.status_code == 200
        assert result.json()["changed"] == [] and not result.json().get("revision")
        assert await revision_rows(response) == []
        after = await container.form_response_repo().get_response(response.response_id)
        assert after.updated_at == before.updated_at

    async def test_only_the_changed_questions_are_recorded(self, client, case):
        workspace, form, response = case
        await edit(client, case, {"city": text("Delft"), "name": text("Ada")})
        [entry] = await revision_rows(response)
        assert entry.changed == ["city"]

    async def test_entries_are_numbered_in_order(self, client, case):
        for value in ("Delft", "Breda", "Zwolle"):
            assert (await edit(client, case, {"city": text(value)})).status_code == 200
        entries = await revision_rows(case[2])
        assert [e.seq for e in entries] == [1, 2, 3]

    async def test_the_answer_can_be_given_where_there_was_none(self, client, case):
        await edit(client, case, {"note": text("Hello")})
        [entry] = await revision_rows(case[2])
        assert entry.changed == ["note"]
        # the previous value of a question that had no answer is null
        from tests.app.controllers.data import testUser

        values = await client.get(revisions_url(*case, seq=1), cookies=cookies(testUser))
        assert values.json()["values"] == {"note": None}

    async def test_the_edit_is_not_announced_or_sent_on(self, client, case, monkeypatch):
        sent = []

        async def post(self, url, **kwargs):
            sent.append(url)
            return {}

        monkeypatch.setattr(type(container.http_client()), "post", post)
        await edit(client, case, {"city": text("Delft")})
        assert sent == []

    async def test_the_response_is_another_workspaces_is_404(
        self, client, case, workspace_1
    ):
        workspace, form, response = case
        from tests.app.controllers.data import testUser1

        result = await client.patch(
            answers_url(workspace_1, form, response),
            json={"answers": {"city": text("x")}},
            cookies=cookies(testUser1),
        )
        assert result.status_code == 404

    async def test_an_unknown_response_is_404(self, client, case):
        workspace, form, response = case
        from tests.app.controllers.data import testUser

        url = answers_url(workspace, form, response).rsplit("/", 2)[0] + "/" + "6" * 24 + "/answers"
        result = await client.patch(
            url, json={"answers": {"city": text("x")}}, cookies=cookies(testUser)
        )
        assert result.status_code == 404


class TestValidationLikeTheRespondent:
    """The same cases go through the respondent's own edit and a staff edit:
    both are refused, with the same status, for the same reason."""

    CASES = {
        "required cleared": {"name": text("")},
        "number above its maximum": {"age": number(500)},
        "number below its minimum": {"age": number(-1)},
        "text in a number": {"age": text("old")},
    }

    @pytest.mark.parametrize("name", list(CASES))
    async def test_both_edits_are_refused_alike(self, client, case, name):
        workspace, form, response = case
        answers = self.CASES[name]
        with pytest.raises(HTTPException) as respondent:
            await respondent_edit(workspace, form, response, answers)
        staff = await edit(client, case, answers)
        assert staff.status_code == respondent.value.status_code == 422, staff.text
        assert await revision_rows(response) == []
        assert (await stored_answers(workspace, response))["name"]["text"] == "Ada"

    async def test_an_unknown_question_is_dropped_like_the_respondents(
        self, client, case
    ):
        workspace, form, response = case
        result = await edit(client, case, {"nope": text("x"), "city": text("Delft")})
        assert result.json()["changed"] == ["city"]
        assert "nope" not in await stored_answers(workspace, response)

    async def test_a_value_a_rule_locks_stays_the_servers(self, workspace, client):
        # a set-value rule fills "city" while "name" is Ada: an edit cannot override it
        from backend.config import settings as s

        s.FIELD_RULES_ENABLED = True
        try:
            rule = {
                "id": "r1",
                "when": {"conditions": [{"fieldId": "name", "comparison": "IS_EQUAL", "value": "Ada"}]},
                "then": {"setValue": {"const": "Lovelace"}, "readOnly": True},
            }
            form = await published_form(
                workspace, [NAME, question("city", properties={"rules": [rule]})]
            )
        finally:
            s.FIELD_RULES_ENABLED = False
        response = await submit(workspace, form, {"name": text("Ada"), "city": text("Lovelace")})
        case = (workspace, form, response)
        result = await edit(client, case, {"city": text("Elsewhere")})
        assert result.status_code in (200, 422)
        assert (await stored_answers(workspace, response))["city"]["text"] == "Lovelace"

    async def test_an_internal_question_is_not_written_here(self, workspace, client):
        internal = question("ref", title="Reference", internal=True)
        form = await published_form(workspace, [NAME, internal])
        response = await submit(workspace, form, {"name": text("Ada")})
        case = (workspace, form, response)
        result = await edit(client, case, {"ref": text("A-1")})
        assert result.status_code == 200
        assert result.json()["changed"] == []
        assert "ref" not in await stored_answers(workspace, response)


class TestWhatStaffCannotChange:
    async def test_a_signature_is_refused(self, workspace, client, monkeypatch):
        monkeypatch.setattr(settings, "SIGNATURE_QUESTION_ENABLED", True)
        sig = question("sig", "signature", title="Sign", properties={"signatureMethods": ["typed"]})
        form = await published_form(workspace, [NAME, sig])
        response = await submit(
            workspace,
            form,
            {
                "name": text("Ada"),
                "sig": {"type": "signature", "signature": {"method": "typed", "name": "Ada Lovelace"}},
            },
        )
        case = (workspace, form, response)
        refused = await edit(
            client,
            case,
            {"sig": {"type": "signature", "signature": {"method": "typed", "name": "Someone Else"}}},
        )
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "question_not_editable"
        assert refused.json()["questionIds"] == ["sig"]
        # neither clearing it
        cleared = await edit(client, case, {"sig": {}})
        assert cleared.status_code == 422
        assert await revision_rows(response) == []
        assert (await stored_answers(workspace, response))["sig"]["signature"]["name"] == "Ada Lovelace"

    async def test_a_file_question_is_refused(self, workspace, client):
        upload = question("doc", "file_upload", title="Document")
        form = await published_form(workspace, [NAME, upload])
        response = await submit(workspace, form, {"name": text("Ada")})
        refused = await edit(
            client,
            (workspace, form, response),
            {"doc": {"type": "file_upload", "file_metadata": {"id": "x", "name": "a.pdf"}}},
        )
        assert refused.status_code == 422
        assert refused.json()["code"] == "question_not_editable"

    async def test_a_response_with_a_pending_deletion_request_is_refused(
        self, client, case
    ):
        workspace, form, response = case
        repo = container.form_response_repo()
        stored = await repo.get_response(response.response_id)
        await repo.add_deletion_request(stored, response.response_id)
        refused = await edit(client, case, {"city": text("Delft")})
        assert refused.status_code == 409
        assert refused.json()["code"] == "deletion_requested"
        assert (await stored_answers(workspace, response))["city"]["text"] == "Leiden"

    async def test_a_declined_deletion_request_does_not_block_it(self, client, case):
        workspace, form, response = case
        repo = container.form_response_repo()
        stored = await repo.get_response(response.response_id)
        request = await repo.add_deletion_request(stored, response.response_id)
        from backend.app.schemas.standard_form_response import DeletionRequestStatus

        request.status = DeletionRequestStatus.DECLINED
        # (closed in place: the privacy flow that declines is not under test)
        from backend.db.models import ResponseDeletionRequestRow

        await repo.upsert(request, row=ResponseDeletionRequestRow)
        ok = await edit(client, case, {"city": text("Delft")})
        assert ok.status_code == 200

    async def test_an_imported_form_is_refused(self, client, workspace):
        form = await published_form(workspace)
        response = await submit(workspace, form, {"name": text("Ada")})
        association = await container.workspace_form_repo().find_workspace_form(
            workspace.id, str(form.form_id)
        )
        association.settings.provider = "google"
        await container.workspace_form_repo().save(association)
        refused = await edit(client, (workspace, form, response), {"name": text("Eve")})
        assert refused.status_code == 409
        assert refused.json()["code"] == "not_editable"


class TestWhichVersion:
    async def test_staff_edit_a_question_the_latest_version_no_longer_has(
        self, client, workspace
    ):
        service = container.workspace_form_service()
        form = await published_form(workspace, [NAME, CITY])
        response = await submit(workspace, form, {"name": text("Ada"), "city": text("Leiden")})
        # version 2 drops the city question
        from common.models.standard_form import StandardForm

        draft = await container.form_service().get_form_document_by_id(str(form.form_id))
        newer = StandardForm(**draft.model_dump())
        newer.fields[0].properties.fields = [f for f in newer.fields[0].properties.fields if f.id != "city"]
        await service.update_form(workspace.id, form.form_id, newer, STAFF_USER)
        await service.publish_form(workspace.id, form.form_id, STAFF_USER)
        assert (await container.form_repo().get_latest_version_of_form(form.form_id)).version == 2
        # staff edit it (the version the response was given in is the reference) ...
        case = (workspace, form, response)
        staff = await edit(client, case, {"city": text("Delft")})
        assert staff.status_code == 200 and staff.json()["changed"] == ["city"]
        # ... the respondent's own edit validates against the latest, which has no such question
        await respondent_edit(workspace, form, response, {"name": text("Ada L")})
        await respondent_edit(workspace, form, response, {"city": text("Gone")})
        assert (await stored_answers(workspace, response))["city"]["text"] == "Delft"


from tests.app.controllers.data import testUser as STAFF_USER  # noqa: E402


class TestRespondentEditsAreLogged:
    async def test_a_respondents_edit_writes_an_entry_with_no_id(self, case):
        workspace, form, response = case
        await respondent_edit(workspace, form, response, {"city": text("Utrecht")})
        [entry] = await revision_rows(response)
        assert entry.actor_kind.value == "respondent"
        assert entry.actor_id is None and entry.actor_role is None
        assert entry.changed == ["city"]

    async def test_a_respondent_edit_that_changes_nothing_writes_no_entry(self, case):
        workspace, form, response = case
        await respondent_edit(workspace, form, response, {"city": text("Leiden")})
        assert await revision_rows(response) == []

    async def test_both_kinds_share_one_numbering(self, client, case):
        workspace, form, response = case
        await respondent_edit(workspace, form, response, {"city": text("Utrecht")})
        await edit(client, case, {"city": text("Delft")})
        await respondent_edit(workspace, form, response, {"note": text("hi")})
        entries = await revision_rows(response)
        assert [(e.seq, e.actor_kind.value) for e in entries] == [
            (1, "respondent"),
            (2, "staff"),
            (3, "respondent"),
        ]

    async def test_the_edit_and_its_entry_commit_together(self, case, monkeypatch):
        workspace, form, response = case
        from backend.app.repositories.postgres import responses

        async def boom(*args, **kwargs):
            raise RuntimeError("the log write fails")

        monkeypatch.setattr(
            responses.PostgresFormResponseRepository, "_write_revision", boom
        )
        with pytest.raises(RuntimeError):
            await respondent_edit(workspace, form, response, {"city": text("Utrecht")})
        # the answer was not changed either
        assert (await stored_answers(workspace, response))["city"]["text"] == "Leiden"
        assert await revision_rows(response) == []

    async def test_a_response_keeps_at_most_the_limit_and_the_edit_is_refused_after(
        self, client, case, monkeypatch
    ):
        from backend.app.repositories.postgres import responses

        monkeypatch.setattr(responses, "MAX_REVISIONS", 2)
        workspace, form, response = case
        for value in ("a", "b"):
            assert (await edit(client, case, {"city": text(value)})).status_code == 200
        refused = await edit(client, case, {"city": text("c")})
        assert refused.status_code == 409 and refused.json()["code"] == "revision_limit"
        assert (await stored_answers(workspace, response))["city"]["text"] == "b"
        assert len(await revision_rows(response)) == 2
