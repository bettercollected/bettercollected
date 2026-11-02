"""What had to land before RESPONSE_REVISIONS_ENABLED goes on: the deletion
request is judged under the response's lock, a staff edit can carry the history
number it was made on, only an allow-list of types is writable, and staff edits
and every read of previous values are audited (ids only)."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from loguru import logger
from sqlalchemy import text as sql

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_audit_event import (
    RESPONSE_REVISION_READ,
    RESPONSE_STAFF_EDIT,
    SSO_BREAK_GLASS_REQUEST,
    SSO_EVENTS,
    WorkspaceAuditEventDocument,
)
from backend.app.services.workspace_form_service import (
    STAFF_WRITABLE_TYPES,
    _not_staff_editable,
)
from common.ids import RecordId
from tests.app.controllers.data import testUser
from tests.app.response_revisions.helpers import (
    answers_url,
    cookies,
    published_form,
    respondent_edit,
    revision_rows,
    revisions_url,
    stored_answers,
    submit,
    text,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def case(workspace):
    form = await published_form(workspace)
    response = await submit(workspace, form, {"name": text("Ada"), "city": text("Leiden")})
    return workspace, form, response


async def patch(client, case, answers, **extra):
    workspace, form, response = case
    return await client.patch(
        answers_url(workspace, form, response),
        json={"answers": answers, **extra},
        cookies=cookies(testUser),
    )


async def audit_rows(workspace):
    async with container.pg_sessionmaker()() as session:
        rows = (
            await session.execute(
                sql("select doc from app.workspace_audit_events where workspace_id = :w order by created_at"),
                {"w": str(workspace.id)},
            )
        ).scalars().all()
    return rows


class TestDeletionRequestUnderTheLock:
    async def test_a_request_filed_after_the_service_looked_still_refuses(
        self, client, case, monkeypatch
    ):
        workspace, form, response = case
        repo = container.form_response_repo()
        stored = await repo.get_response(response.response_id)
        await repo.add_deletion_request(stored, response.response_id)
        # the service's early look finds nothing (the request came after it)
        async def none(self, existing):
            return None

        monkeypatch.setattr(type(container.form_response_service()), "deletion_request_of", none)
        refused = await patch(client, case, {"city": text("Delft")})
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "deletion_requested"
        assert (await stored_answers(workspace, response))["city"]["text"] == "Leiden"
        assert await revision_rows(response) == []

    async def test_an_edit_and_a_request_made_at_once_never_both_win(
        self, client, case
    ):
        workspace, form, response = case
        repo = container.form_response_repo()
        stored = await repo.get_response(response.response_id)
        service = container.workspace_form_service()
        lock = container.pg_sessionmaker()()
        await lock.begin()
        await lock.execute(
            sql("select 1 from app.form_responses where id = :i for update"), {"i": str(stored.id)}
        )

        async def edit():
            try:
                await service.staff_edit_answers(
                    workspace.id, form.form_id, response.response_id, {"city": text("Delft")}, testUser
                )
                return 200
            except HTTPException as error:
                return error.status_code

        edit_task = asyncio.create_task(edit())
        request_task = asyncio.create_task(repo.add_deletion_request(stored, response.response_id))
        await asyncio.sleep(0.3)
        await lock.commit()
        await lock.close()
        status = await edit_task
        await request_task
        city = (await stored_answers(workspace, response))["city"]["text"]
        # either the edit went first (stored, then the request) or the request
        # did and the edit was refused: never an edit stored under a pending request
        assert (status, city) in ((200, "Delft"), (409, "Leiden"))
        again = await patch(client, case, {"city": text("Zwolle")})
        assert again.status_code == 409 and again.json()["code"] == "deletion_requested"

    async def test_a_declined_request_does_not_block(self, client, case):
        from backend.app.schemas.standard_form_response import DeletionRequestStatus
        from backend.db.models import ResponseDeletionRequestRow

        workspace, form, response = case
        repo = container.form_response_repo()
        stored = await repo.get_response(response.response_id)
        request = await repo.add_deletion_request(stored, response.response_id)
        request.status = DeletionRequestStatus.DECLINED
        await repo.upsert(request, row=ResponseDeletionRequestRow)
        assert (await patch(client, case, {"city": text("Delft")})).status_code == 200


class TestExpectedSeq:
    async def test_the_number_the_editor_saw_must_still_be_the_newest(self, client, case):
        workspace, form, response = case
        first = await patch(client, case, {"city": text("Delft")}, expectedSeq=0)
        assert first.status_code == 200 and first.json()["revision"] == 1
        stale = await patch(client, case, {"city": text("Breda")}, expectedSeq=0)
        assert stale.status_code == 409, stale.text
        assert stale.json()["code"] == "response_changed" and stale.json()["currentSeq"] == 1
        assert (await stored_answers(workspace, response))["city"]["text"] == "Delft"
        ok = await patch(client, case, {"city": text("Breda")}, expectedSeq=1)
        assert ok.status_code == 200 and ok.json()["revision"] == 2

    async def test_a_respondents_edit_in_between_is_a_change_too(self, client, case):
        workspace, form, response = case
        await respondent_edit(workspace, form, response, {"city": text("Utrecht")})
        stale = await patch(client, case, {"city": text("Delft")}, expectedSeq=0)
        assert stale.status_code == 409 and stale.json()["currentSeq"] == 1
        assert (await stored_answers(workspace, response))["city"]["text"] == "Utrecht"

    async def test_without_it_there_is_no_check(self, client, case):
        for value in ("a", "b"):
            assert (await patch(client, case, {"city": text(value)})).status_code == 200

    @pytest.mark.parametrize("bad", [-1, "x", 1.5, 10**9])
    async def test_a_bad_number_is_422(self, client, case, bad):
        assert (await patch(client, case, {"city": text("x")}, expectedSeq=bad)).status_code == 422

    async def test_a_refused_check_writes_nothing_else(self, client, case):
        workspace, form, response = case
        await patch(client, case, {"city": text("Delft")}, expectedSeq=0)
        await patch(client, case, {"city": text("Breda")}, expectedSeq=0)
        assert len(await revision_rows(response)) == 1
        # the refused edit is not audited as an edit
        events = [json.loads(json.dumps(r))["event"] for r in await audit_rows(workspace)]
        assert events.count(RESPONSE_STAFF_EDIT) == 1


def fake_form(**types):
    fields = [SimpleNamespace(id=name, type=kind, properties=SimpleNamespace(fields=None, share_as_choices=None)) for name, kind in types.items()]
    return SimpleNamespace(fields=[SimpleNamespace(id="p", type="slide", properties=SimpleNamespace(fields=fields))])


class TestAllowList:
    def test_the_allow_list_is_the_types_the_dialog_offers(self):
        assert STAFF_WRITABLE_TYPES == {
            "short_text", "long_text", "number", "date", "email", "url",
            "phone_number", "multiple_choice", "dropdown", "yes_no",
        }

    @pytest.mark.parametrize("kind", sorted(STAFF_WRITABLE_TYPES))
    def test_each_writable_type_passes(self, kind):
        assert _not_staff_editable([fake_form(q=kind)], {"q": {}}) == []

    @pytest.mark.parametrize(
        "kind",
        ["payment", "hidden", "signature", "file_upload", "input_file_upload", "address", "matrix",
         "group", "ranking", "tabular_input", "rating", "opinion_scale", "linear_rating", "tags",
         "currency", "time", "day", "date_range", "calculated", "statement", "banana", "", None],
    )
    def test_everything_else_and_any_unknown_type_is_refused(self, kind):
        assert _not_staff_editable([fake_form(q=kind)], {"q": {}}) == ["q"]

    def test_a_type_writable_in_one_version_but_not_the_other_is_refused(self):
        assert _not_staff_editable([fake_form(q="short_text"), fake_form(q="payment")], {"q": {}}) == ["q"]
        assert _not_staff_editable([None, fake_form(q="short_text")], {"q": {}}) == []

    def test_an_id_no_version_has_is_left_to_the_edit_to_drop(self):
        assert _not_staff_editable([fake_form(q="short_text")], {"nope": {}}) == []

    async def test_through_the_route_a_matrix_question_is_refused(self, client, workspace):
        from tests.app.response_revisions.helpers import NAME, question

        form = await published_form(
            workspace, [NAME, question("grid", "matrix", title="Grid", properties={"rowTitles": ["a"], "columnTitles": ["b"]})]
        )
        response = await submit(workspace, form, {"name": text("Ada")})
        refused = await patch(client, (workspace, form, response), {"grid": {"type": "matrix"}})
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "question_not_editable" and refused.json()["questionIds"] == ["grid"]


class TestAudit:
    async def test_a_staff_edit_is_one_entry_with_ids_and_no_value(self, client, case):
        workspace, form, response = case
        await patch(client, case, {"city": text("Delft")})
        [row] = [r for r in await audit_rows(workspace) if r["event"] == RESPONSE_STAFF_EDIT]
        assert row["form_id"] == str(form.form_id) and row["response_id"] == response.response_id
        assert row["revision"] == 1 and row["user_id"] == str(testUser.id)
        everything = json.dumps(await audit_rows(workspace))
        for secret in ("Delft", "Leiden", "Ada", "city"):
            assert secret not in everything

    async def test_an_edit_that_changes_nothing_is_not_audited(self, client, case):
        workspace, *_ = case
        await patch(client, case, {"city": text("Leiden")})
        assert [r for r in await audit_rows(workspace) if r["event"] == RESPONSE_STAFF_EDIT] == []

    async def test_a_read_of_previous_values_is_audited_before_it_is_served(self, client, case):
        workspace, form, response = case
        await patch(client, case, {"city": text("Delft")})
        got = await client.get(revisions_url(workspace, form, response, 1), cookies=cookies(testUser))
        assert got.status_code == 200 and got.json()["values"]["city"]["text"] == "Leiden"
        reads = [r for r in await audit_rows(workspace) if r["event"] == RESPONSE_REVISION_READ]
        assert len(reads) == 1 and reads[0]["revision"] == 1 and reads[0]["response_id"] == response.response_id
        for secret in ("Delft", "Leiden", "Ada"):
            assert secret not in json.dumps(await audit_rows(workspace))
        # every read, not the first only
        await client.get(revisions_url(workspace, form, response, 1), cookies=cookies(testUser))
        assert len([r for r in await audit_rows(workspace) if r["event"] == RESPONSE_REVISION_READ]) == 2

    async def test_the_list_without_values_is_not_a_read_of_values(self, client, case):
        workspace, form, response = case
        await patch(client, case, {"city": text("Delft")})
        await client.get(revisions_url(workspace, form, response), cookies=cookies(testUser))
        assert [r for r in await audit_rows(workspace) if r["event"] == RESPONSE_REVISION_READ] == []

    async def test_a_read_that_cannot_be_recorded_is_refused_and_serves_no_value(
        self, client, case, monkeypatch
    ):
        workspace, form, response = case
        await patch(client, case, {"city": text("Delft")})

        async def broken(self, document):
            raise RuntimeError("the audit table is down")

        monkeypatch.setattr(type(container.workspace_audit_repo()), "record", broken)
        refused = await client.get(revisions_url(workspace, form, response, 1), cookies=cookies(testUser))
        assert refused.status_code == 503 and refused.json()["code"] == "audit_unavailable"
        assert "Leiden" not in refused.text

    async def test_an_edit_whose_audit_fails_stays_stored_and_logs_ids_only(
        self, client, case, monkeypatch
    ):
        workspace, form, response = case
        lines = []
        sink = logger.add(lambda message: lines.append(str(message)), level="ERROR")

        async def broken(self, document):
            raise RuntimeError("the audit table is down")

        monkeypatch.setattr(type(container.workspace_audit_repo()), "record", broken)
        try:
            ok = await patch(client, case, {"city": text("Delft")})
        finally:
            logger.remove(sink)
        assert ok.status_code == 200
        assert (await stored_answers(workspace, response))["city"]["text"] == "Delft"
        logged = "\n".join(lines)
        assert "NOT STORED" in logged and response.response_id in logged
        for secret in ("Delft", "Leiden", "Ada"):
            assert secret not in logged

    async def test_the_single_sign_on_page_lists_only_its_own_events(self, workspace):
        repo = container.workspace_audit_repo()
        for event in (SSO_BREAK_GLASS_REQUEST, RESPONSE_STAFF_EDIT):
            await repo.record(
                WorkspaceAuditEventDocument(
                    id=RecordId(), workspace_id=workspace.id, user_id="u1", event=event
                )
            )
        kinds = {e.event for e in await repo.page(workspace.id, 10, None, events=SSO_EVENTS)}
        assert kinds == {SSO_BREAK_GLASS_REQUEST}
        assert {e.event for e in await repo.page(workspace.id, 10, None)} == {
            SSO_BREAK_GLASS_REQUEST,
            RESPONSE_STAFF_EDIT,
        }


class TestRedactionSaysWhatItSkipped:
    async def test_an_entry_that_cannot_be_opened_is_counted_in_a_warning(self, workspace):
        form = await published_form(workspace)
        response = await submit(workspace, form, {"name": text("Ada")})
        await respondent_edit(workspace, form, response, {"name": text("B")})
        [entry] = await revision_rows(response)
        entry.previous_values = b"v1:this is not a sealed value"
        await container.response_revision_repo().upsert(entry)
        lines = []
        sink = logger.add(lambda message: lines.append(str(message)), level="WARNING")
        try:
            changed = await container.form_response_repo().redact_history_option_labels(
                [entry.response_pk], workspace.id, str(form.form_id), ["name"], {"x"}
            )
        finally:
            logger.remove(sink)
        assert changed == 0
        logged = "\n".join(lines)
        assert "1 history entry of 1 response(s) could not be read" in logged
        assert "Ada" not in logged
