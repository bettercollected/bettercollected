"""Writes of the responses group that read before they write apply to the
stored row, never to a copy read earlier (locked rows, advisory locks on a
natural key, one transaction per change), and answers stay encrypted at rest.
Skipped unless DATABASE_URL points at a *_test database."""

import asyncio
import json
from contextlib import suppress

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.repositories.postgres.responses import (
    _advisory_lock,
    _busy_on_lock_timeout,
    PostgresFormResponseRepository,
    PostgresResponderGroupsRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.repositories.response_scope import ResponseScope
from backend.app.schemas.standard_form_response import (
    DeclineReason,
    DeletionRequestStatus,
    FormResponseDeletionRequest,
    FormResponseDocument,
    staff_closure,
)
from backend.db.models import (
    FormResponseRow,
    ResponderGroupFormRow,
    ResponderGroupMemberRow,
    ResponderGroupRow,
    ResponseDeletionRequestRow,
    WorkspaceResponderRow,
)
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from common.clock import utcnow
from common.records import RecordId, row_values
from common.services.crypto_service import crypto_service
from tests.app.repositories.parity import sessions  # noqa: F401

WORKSPACE = RecordId(f"{1:024x}")
FORM = RecordId(f"{2:024x}")
OWNER = User(id=str(RecordId(f"{3:024x}")), sub="owner@example.com")


def responses_repo(sessions):
    return PostgresFormResponseRepository(
        sessions, container.form_repo(), container.workspace_form_repo()
    )


def decrypted(stored: FormResponseDocument) -> dict:
    """The stored answers' texts by question (the answer objects carry more
    fields, all unset here)."""
    answers = json.loads(
        crypto_service.decrypt(
            workspace_id=WORKSPACE, form_id=FORM, data=stored.answers
        )
    )
    return {question: answer["text"] for question, answer in answers.items()}


async def submitted(repo, answers) -> FormResponseDocument:
    return await repo.save_form_response(
        FORM,
        StandardFormResponse(answers=answers, dataOwnerIdentifier=OWNER.sub),
        WORKSPACE,
    )


# ------------------------------------------------------------ encrypted at rest
async def test_answers_are_encrypted_in_the_row_and_stay_so_through_an_edit(sessions):
    repo = responses_repo(sessions)
    stored = await submitted(repo, {"q1": {"text": "first-secret-answer"}})
    await repo.patch_form_response(
        str(FORM),
        stored.id,
        StandardFormResponse(answers={"q2": {"text": "second-secret-answer"}}),
        WORKSPACE,
        OWNER,
    )
    async with sessions() as session:
        raw = (
            await session.execute(
                select(FormResponseRow.doc).where(FormResponseRow.id == str(stored.id))
            )
        ).scalar_one()
    stored_text = json.dumps(raw)
    assert "first-secret-answer" not in stored_text
    assert "second-secret-answer" not in stored_text
    assert set(raw["answers"]) == {"$binary"}  # a ciphertext blob, not the answers
    assert not isinstance((await repo.one(FormResponseRow.id == str(stored.id))).answers, dict)
    row = await repo.one(FormResponseRow.id == str(stored.id))
    assert decrypted(row) == {
        "q1": "first-secret-answer",
        "q2": "second-secret-answer",
    }


# ---------------------------------------------------------------- a response edit
async def test_edits_of_a_response_made_at_once_all_keep_their_answers(sessions):
    repo = responses_repo(sessions)
    stored = await submitted(repo, {"q0": {"text": "kept"}})

    def edit(n):
        return repo.patch_form_response(
            str(FORM),
            stored.id,
            StandardFormResponse(answers={f"q{n}": {"text": f"edit {n}"}}),
            WORKSPACE,
            OWNER,
        )

    await asyncio.gather(*(edit(n) for n in range(1, 7)))
    row = await repo.one(FormResponseRow.id == str(stored.id))
    assert decrypted(row) == {
        "q0": "kept",
        **{f"q{n}": f"edit {n}" for n in range(1, 7)},
    }


async def test_an_edit_made_with_a_feedback_entry_in_between_keeps_it(sessions):
    from common.models.standard_form import RespondentFeedback

    repo = responses_repo(sessions)
    stored = await submitted(repo, {"q0": {"text": "kept"}})
    entry = RespondentFeedback(
        id="e1", status="Selected", created_by="u1", created_by_email="s@example.com"
    )
    await asyncio.gather(
        repo.add_respondent_feedback(stored, entry),
        repo.patch_form_response(
            str(FORM),
            stored.id,
            StandardFormResponse(answers={"q1": {"text": "edit"}}),
            WORKSPACE,
            OWNER,
        ),
    )
    row = await repo.one(FormResponseRow.id == str(stored.id))
    assert [e.id for e in row.respondent_feedback] == ["e1"]
    assert set(decrypted(row)) == {"q0", "q1"}


async def test_only_the_respondent_edits_and_a_missing_response_is_not_found(sessions):
    repo = responses_repo(sessions)
    stored = await submitted(repo, {"q0": {"text": "kept"}})
    body = StandardFormResponse(answers={"q1": {"text": "x"}})
    with pytest.raises(HTTPException) as refused:
        await repo.patch_form_response(
            str(FORM), stored.id, body, WORKSPACE, User(id="x", sub="other@example.com")
        )
    assert refused.value.status_code == 403
    with pytest.raises(HTTPException) as refused:
        await repo.patch_form_response(str(FORM), stored.id, body, WORKSPACE, None)
    assert refused.value.status_code == 403
    with pytest.raises(HTTPException) as missing:
        await repo.patch_form_response(str(FORM), RecordId(), body, WORKSPACE, OWNER)
    assert missing.value.status_code == 404
    row = await repo.one(FormResponseRow.id == str(stored.id))
    assert decrypted(row) == {"q0": "kept"}


# ------------------------------------------------------------ deletion requests
async def filed(repo):
    stored = await submitted(repo, {"q0": {"text": "kept"}})
    stored.response_id = "r1"  # a self-submitted response has none: a provider's does
    await repo.save(stored)
    request = await repo.add_deletion_request(stored, "r1")
    return stored, request


def scope():
    return ResponseScope(WORKSPACE, (str(FORM),))


async def test_a_request_closed_since_it_was_read_is_refused(sessions):
    repo = responses_repo(sessions)
    _, request = await filed(repo)
    (first,) = await repo.list_deletion_requests_for_form_ids(scope())
    (second,) = await repo.list_deletion_requests_for_form_ids(scope())
    closed = await repo.close_deletion_request(
        first, DeletionRequestStatus.DECLINED, "staff-1", DeclineReason.OTHER
    )
    assert closed.status == DeletionRequestStatus.DECLINED
    with pytest.raises(HTTPException) as refused:
        await repo.close_deletion_request(
            second, DeletionRequestStatus.SUCCESS, "staff-2"
        )
    assert refused.value.status_code == 409
    assert refused.value.content["code"] == "deletion_request_closed"
    (stored,) = await repo.list_deletion_requests_for_form_ids(scope())
    assert stored.status == DeletionRequestStatus.DECLINED
    assert [c.by for c in stored.closures] == ["staff-1"]
    assert stored.closed_by == "staff-1"


async def test_two_closes_made_at_once_record_one(sessions):
    repo = responses_repo(sessions)
    await filed(repo)
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    outcomes = await asyncio.gather(
        *(
            repo.close_deletion_request(
                read, DeletionRequestStatus.DECLINED, f"staff-{n}", DeclineReason.OTHER
            )
            for n in range(4)
        ),
        return_exceptions=True,
    )
    refused = [o for o in outcomes if isinstance(o, HTTPException)]
    assert len(refused) == 3 and all(o.status_code == 409 for o in refused)
    (stored,) = await repo.list_deletion_requests_for_form_ids(scope())
    assert len(stored.closures) == 1


async def test_completing_a_request_by_deleting_the_response_is_no_conflict(sessions):
    """The staff close that follows a deletion (the service deletes the copy,
    then closes the request it read first) is not a second close."""
    repo = responses_repo(sessions)
    stored, request = await filed(repo)
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    await repo.delete_form_response(stored)
    after_delete = await repo.find_deletion_request_for(stored)
    assert after_delete.status == DeletionRequestStatus.SUCCESS
    assert after_delete.closures == []
    closed = await repo.close_deletion_request(
        read, DeletionRequestStatus.SUCCESS, "staff-1"
    )
    assert closed.status == DeletionRequestStatus.SUCCESS
    assert [c.by for c in closed.closures] == ["staff-1"]
    assert await repo.list_by_response_id("r1") == []


async def test_closing_a_request_that_is_gone_is_not_found(sessions):
    repo = responses_repo(sessions)
    stored, request = await filed(repo)
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    await repo.delete_deletion_requests(str(FORM))
    with pytest.raises(HTTPException) as missing:
        await repo.close_deletion_request(
            read, DeletionRequestStatus.DECLINED, "staff", DeclineReason.OTHER
        )
    assert missing.value.status_code == 404
    assert await repo.list_deletion_requests_for_form_ids(scope()) == []


async def test_an_import_refresh_keeps_a_staff_decline_and_adds_its_own_close(
    sessions,
):
    from datetime import datetime, timezone

    repo = responses_repo(sessions)
    stored = await repo.save(
        FormResponseDocument(
            form_id=str(FORM),
            response_id="gone",
            answers={},
            provider="google",
            workspace_id=WORKSPACE,
        )
    )
    await repo.add_deletion_request(stored, "gone")
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    await repo.close_deletion_request(
        read, DeletionRequestStatus.DECLINED, "staff-1", DeclineReason.LEGAL_CLAIMS
    )
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert (
        await repo.mark_deletion_requests_success_except(scope(), "google", [], now)
        == 1
    )
    (stored_request,) = await repo.list_deletion_requests_for_form_ids(scope())
    assert stored_request.status == DeletionRequestStatus.SUCCESS
    assert [(c.source, c.status) for c in stored_request.closures] == [
        ("staff", "declined"),
        ("import", "success"),
    ]
    assert stored_request.decline_reason == DeclineReason.LEGAL_CLAIMS


# ------------------------------------------------------ responders, tags, groups
async def test_a_tag_created_at_once_is_stored_once(sessions):
    repo = PostgresWorkspaceRespondersRepository(sessions)
    tags = await asyncio.gather(*(repo.create_workspace_tag(WORKSPACE, "vip") for _ in range(8)))
    assert len({str(t.id) for t in tags}) == 1
    assert [t.title for t in await repo.get_workspace_tags(WORKSPACE)] == ["vip"]
    await repo.create_workspace_tag(WORKSPACE, "other")
    assert len(await repo.get_workspace_tags(WORKSPACE)) == 2


async def test_a_responder_written_at_once_is_stored_once_and_keeps_every_field(
    sessions,
):
    repo = PostgresWorkspaceRespondersRepository(sessions)
    tag = RecordId(f"{9:024x}")
    await asyncio.gather(
        repo.patch_responder(WORKSPACE, "a@example.com", {"team": "x"}, None),
        repo.patch_responder(WORKSPACE, "a@example.com", None, [tag]),
        repo.get_responder_by_email_and_workspace_id(WORKSPACE, "a@example.com"),
        repo.get_responder_by_email_and_workspace_id(WORKSPACE, "a@example.com"),
    )
    rows = await repo.many(
        WorkspaceResponderRow.workspace_id == str(WORKSPACE),
        WorkspaceResponderRow.email == "a@example.com",
    )
    assert len(rows) == 1
    assert (rows[0].metadata, rows[0].tags) == ({"team": "x"}, [tag])


async def test_a_failed_group_update_leaves_the_members_as_they_were(
    sessions, monkeypatch
):
    repo = PostgresResponderGroupsRepository(sessions)
    group = await repo.create_group(WORKSPACE, "Team")
    await repo.add_emails_to_group(group.id, ["a@x.com", "b@x.com"])

    real = repo._upsert_statement
    calls = []

    def failing(values, row=None):
        if row is ResponderGroupMemberRow:
            calls.append(values["id"])
            if len(calls) == 2:
                raise RuntimeError("the store went away")
        return real(values, row)

    monkeypatch.setattr(repo, "_upsert_statement", failing)
    with pytest.raises(RuntimeError):
        await repo.update_group(
            WORKSPACE, "Renamed", None, ["c@x.com", "d@x.com", "e@x.com"], group.id
        )
    monkeypatch.undo()
    info = await repo.get_emails_in_group(group.id)
    assert sorted(info["emails"]) == ["a@x.com", "b@x.com"]
    assert info["name"] == "Team"


async def test_a_group_of_another_workspace_is_not_updated(sessions):
    repo = PostgresResponderGroupsRepository(sessions)
    group = await repo.create_group(WORKSPACE, "Team")
    with pytest.raises(HTTPException) as missing:
        await repo.update_group(RecordId(), "Hijacked", None, ["x@x.com"], group.id)
    assert missing.value.status_code == 404
    assert (await repo.get_emails_in_group(group.id))["name"] == "Team"


async def test_groups_saved_on_one_form_at_once_leave_one_of_the_sets(sessions):
    repo = PostgresResponderGroupsRepository(sessions)
    a, b, c = [await repo.create_group(WORKSPACE, n) for n in ("A", "B", "C")]
    form = "form-1"
    await asyncio.gather(
        *(
            [repo.add_groups_to_form(form, [a.id, b.id]) for _ in range(3)]
            + [repo.add_groups_to_form(form, [c.id]) for _ in range(3)]
        )
    )
    linked = {str(g["_id"]) for g in (await repo.get_groups_by_form_ids([form]))[form]}
    assert linked in ({str(a.id), str(b.id)}, {str(c.id)})


async def test_removing_a_group_removes_its_members_and_links_together(sessions):
    repo = PostgresResponderGroupsRepository(sessions)
    group = await repo.create_group(WORKSPACE, "Team")
    await repo.add_emails_to_group(group.id, ["a@x.com"])
    await repo.add_group_to_form("f1", group.id)
    await repo.remove_responder_group(group.id)
    assert await repo.get_emails_in_group(group.id) is None
    async with sessions() as session:
        members = (
            await session.execute(
                select(ResponderGroupMemberRow.id).where(
                    ResponderGroupMemberRow.group_id == str(group.id)
                )
            )
        ).all()
        groups = (
            await session.execute(
                select(ResponderGroupRow.id).where(ResponderGroupRow.id == str(group.id))
            )
        ).all()
    assert members == [] and groups == []
    assert (await repo.get_groups_by_form_ids(["f1"]))["f1"] == []


# ----------------------------------------------- deterministic interleavings
async def _wait_for_waiter(sessions):
    """Until a backend of this database waits for a lock."""
    for _ in range(100):
        async with sessions() as session:
            waiting = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE "
                        "wait_event_type = 'Lock' AND datname = current_database()"
                    )
                )
            ).scalar_one()
        if waiting:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("the call never waited for the lock")


async def interleaved(sessions, hold, call, during):
    """Run ``call`` while another transaction holds a lock (``hold``); once
    the call is waiting for it, apply ``during`` in that transaction and let
    it commit. The call's result, or the exception it raised."""
    task = None
    try:
        async with sessions() as session, session.begin():
            await hold(session)
            task = asyncio.ensure_future(call())
            await _wait_for_waiter(sessions)
            await during(session)
    except BaseException:
        if task is not None:
            task.cancel()
            with suppress(BaseException):
                await task
        raise
    return (await asyncio.gather(task, return_exceptions=True))[0]


def lock_request(row_id):
    async def hold(session):
        await session.execute(
            select(ResponseDeletionRequestRow.doc)
            .where(ResponseDeletionRequestRow.id == str(row_id))
            .with_for_update()
        )

    return hold


def decline_by_staff(repo, read: FormResponseDeletionRequest):
    """What a staff close committed meanwhile leaves on the request."""

    async def during(session):
        declined = read.model_copy(deep=True)
        declined.status = DeletionRequestStatus.DECLINED
        declined.closed_by = "staff-1"
        declined.decline_reason = DeclineReason.OTHER
        declined.closures = [
            staff_closure(
                DeletionRequestStatus.DECLINED, "staff-1", utcnow(), DeclineReason.OTHER
            )
        ]
        declined.touch()
        await session.execute(
            repo._upsert_statement(row_values(declined), ResponseDeletionRequestRow)
        )

    return during


async def test_completing_a_request_deletes_nothing_under_a_concurrent_decline(
    sessions,
):
    repo = responses_repo(sessions)
    stored, _ = await filed(repo)
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    outcome = await interleaved(
        sessions,
        lock_request(read.id),
        lambda: repo.delete_form_response(stored, expected_closures=len(read.closures)),
        decline_by_staff(repo, read),
    )
    assert isinstance(outcome, HTTPException) and outcome.status_code == 409
    assert outcome.content["code"] == "deletion_request_closed"
    assert len(await repo.list_by_response_id("r1")) == 1  # the data is still there
    (request,) = await repo.list_deletion_requests_for_form_ids(scope())
    assert request.status == DeletionRequestStatus.DECLINED
    assert [c.source for c in request.closures] == ["staff"]


async def test_a_completion_that_saw_no_decline_deletes_and_marks_success(sessions):
    """Without a close in between, the same call deletes the copy and marks
    the request done; a plain deletion (no expectation) always does."""
    repo = responses_repo(sessions)
    stored, _ = await filed(repo)
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    await repo.delete_form_response(stored, expected_closures=len(read.closures))
    assert await repo.list_by_response_id("r1") == []
    (request,) = await repo.list_deletion_requests_for_form_ids(scope())
    assert request.status == DeletionRequestStatus.SUCCESS


async def test_the_import_refresh_waits_for_a_concurrent_staff_close_and_keeps_it(
    sessions,
):
    from datetime import datetime, timezone

    repo = responses_repo(sessions)
    await filed(repo)
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    outcome = await interleaved(
        sessions,
        lock_request(read.id),
        lambda: repo.mark_deletion_requests_success_except(scope(), "self", [], now),
        decline_by_staff(repo, read),
    )
    assert outcome == 1
    (request,) = await repo.list_deletion_requests_for_form_ids(scope())
    assert request.status == DeletionRequestStatus.SUCCESS
    assert [(c.source, c.status) for c in request.closures] == [
        ("staff", "declined"),
        ("import", "success"),
    ]
    assert request.decline_reason == DeclineReason.OTHER


async def test_a_staff_close_after_the_import_refresh_is_refused(sessions):
    from datetime import datetime, timezone

    repo = responses_repo(sessions)
    await filed(repo)
    (read,) = await repo.list_deletion_requests_for_form_ids(scope())
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    await repo.mark_deletion_requests_success_except(scope(), "self", [], now)
    with pytest.raises(HTTPException) as refused:
        await repo.close_deletion_request(
            read, DeletionRequestStatus.DECLINED, "staff-1", DeclineReason.OTHER
        )
    assert refused.value.status_code == 409
    (request,) = await repo.list_deletion_requests_for_form_ids(scope())
    assert [c.source for c in request.closures] == ["import"]


async def test_groups_saved_on_a_form_wait_for_the_save_in_progress(sessions):
    """A save of a form's groups reads the links only once the save before it
    has committed: here another save links group C meanwhile, and this one,
    setting {A, B}, removes it."""
    repo = PostgresResponderGroupsRepository(sessions)
    a, b, c = [await repo.create_group(WORKSPACE, n) for n in ("A", "B", "C")]
    form = "form-1"

    async def hold(session):
        await _advisory_lock(session, "responder_group_form", form)

    async def during(session):
        link = repo.link(c.id, form)
        link.touch()
        await session.execute(
            repo._upsert_statement(row_values(link), ResponderGroupFormRow)
        )

    links = await interleaved(
        sessions, hold, lambda: repo.add_groups_to_form(form, [a.id, b.id]), during
    )
    assert {str(link.group_id) for link in links} == {str(a.id), str(b.id)}
    found = await repo.get_groups_by_form_ids([form])
    assert {str(g["_id"]) for g in found[form]} == {str(a.id), str(b.id)}


async def test_a_group_update_applies_to_the_stored_group_not_to_one_read_before(
    sessions,
):
    repo = PostgresResponderGroupsRepository(sessions)
    group = await repo.create_group(WORKSPACE, "Team", "old description")

    async def hold(session):
        await session.execute(
            select(ResponderGroupRow.doc)
            .where(ResponderGroupRow.id == str(group.id))
            .with_for_update()
        )

    async def during(session):  # another change of a field the update leaves alone
        stored = await repo.get_group_in_workspace(WORKSPACE, group.id)
        stored.description = "changed meanwhile"
        stored.touch()
        await session.execute(
            repo._upsert_statement(row_values(stored), ResponderGroupRow)
        )

    updated = await interleaved(
        sessions,
        hold,
        lambda: repo.update_group(WORKSPACE, "Renamed", None, None, group.id, None),
        during,
    )
    assert (updated.name, updated.description) == ("Renamed", "changed meanwhile")
    stored = await repo.get_group_in_workspace(WORKSPACE, group.id)
    assert (stored.name, stored.description) == ("Renamed", "changed meanwhile")


async def test_deletes_of_overlapping_workspaces_at_once_do_not_deadlock(sessions):
    repo = PostgresResponderGroupsRepository(sessions)
    workspaces = [RecordId() for _ in range(3)]
    for workspace in workspaces:
        for n in range(6):
            await repo.create_group(workspace, f"G{n}")
    outcomes = await asyncio.gather(
        *(
            repo.delete_responder_groups(order)
            for order in (
                workspaces,
                workspaces[::-1],
                workspaces[1:],
                workspaces[:2][::-1],
            )
            * 2
        ),
        return_exceptions=True,
    )
    assert [o for o in outcomes if isinstance(o, BaseException)] == []
    for workspace in workspaces:
        assert await repo.get_groups_in_workspace(workspace) == []


# ----------------------------------------------------------------- lock timeout
class _Orig(Exception):
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate


def test_a_lock_timeout_is_a_retryable_409_and_other_errors_pass_through():
    with pytest.raises(HTTPException) as busy:
        with _busy_on_lock_timeout():
            raise DBAPIError("SELECT 1", {}, _Orig("55P03"))
    assert busy.value.status_code == 409 and busy.value.content["code"] == "busy"
    with pytest.raises(DBAPIError):
        with _busy_on_lock_timeout():
            raise DBAPIError("SELECT 1", {}, _Orig("40001"))
