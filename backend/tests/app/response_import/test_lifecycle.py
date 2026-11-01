"""Undo, retention, the sweep, a worker that dies, a role removed meanwhile,
and the erasure of an account or a form."""

import asyncio
import datetime as dt

import pytest
from common.clock import utcnow
from common.records import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.response_import import DELETED_ACTOR, ImportStatus
from backend.app.services.response_import import limits
from tests.app.controllers.data import testUser
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.response_import.helpers import (
    csv_bytes,
    get,
    import_all,
    post,
    publish_form,
    run_job,
    service,
    stored_answers,
    submit,
    upload,
    url,
)
from tests.app.response_import.test_flow import HEADER, SIMPLE, count, member, simple_form

pytestmark = pytest.mark.asyncio

ROWS = [HEADER, ["Ada", "36", "Red"], ["Bob", "40", "Blue"], ["Cy", "50", "Red"]]


async def rollback(client, workspace, form, import_id, user=testUser):
    return await client.post(url(workspace, form, f"/{import_id}/rollback"), cookies=_cookies(user))


# --------------------------------------------------------------------------- undo


async def test_an_import_can_be_undone_and_only_its_responses_go(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    await submit(workspace, form, {"name": {"type": "text", "text": "Real respondent"}})
    first = await import_all(client, workspace, form, csv_bytes(ROWS))
    second = await import_all(client, workspace, form, csv_bytes([HEADER, ["Dee", "1", "Red"]]))
    assert await count(workspace, form) == 5
    assert first["canRollback"] is True
    undone = await rollback(client, workspace, form, first["id"])
    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert (body["status"], body["rolledBackCount"]) == ("rolled_back", 3)
    names = sorted(
        (r.answers["name"]["text"] if isinstance(r.answers["name"], dict) else r.answers["name"].text)
        for r in await stored_answers(workspace, form)
    )
    assert names == ["Dee", "Real respondent"]
    # the audit keeps who undid it and when
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.rolled_back_by == str(testUser.id) and row.rolled_back_at is not None
    # not twice, and the other import is untouched
    assert (await rollback(client, workspace, form, first["id"])).status_code == 409
    assert (await get(client, workspace, form, second["id"])).json()["status"] == "completed"


async def test_only_a_completed_import_within_the_window_can_be_undone(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    failed = await import_all(client, workspace, form, csv_bytes([HEADER, ["Ada", "999", "Red"]]))
    refused = await rollback(client, workspace, form, failed["id"])
    assert (refused.status_code, refused.json()["code"]) == (409, "not_rollbackable")
    done = await import_all(client, workspace, form, csv_bytes(ROWS))
    later = utcnow() + limits.ROLLBACK_WINDOW + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    expired = await rollback(client, workspace, form, done["id"])
    assert (expired.status_code, expired.json()["code"]) == (409, "rollback_expired")
    assert await count(workspace, form) == 3


async def test_an_undo_is_the_importers_to_ask_by_permission_only(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    done = await import_all(client, workspace, form, csv_bytes(ROWS))
    viewer = await member(workspace, WorkspaceRoles.VIEWER)
    assert (await rollback(client, workspace, form, done["id"], user=viewer)).status_code == 403
    admin = await member(workspace, WorkspaceRoles.ADMIN)
    assert (await rollback(client, workspace, form, done["id"], user=admin)).status_code == 200


async def test_an_undo_makes_the_forms_stored_export_files_go(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    done = await import_all(client, workspace, form, csv_bytes(ROWS))
    called = []

    async def forget(workspace_id, form_id):
        called.append((str(workspace_id), str(form_id)))
        return 0

    monkeypatch.setattr(container.response_export_service(), "forget_files_of_form", forget)
    assert (await rollback(client, workspace, form, done["id"])).status_code == 200
    assert called == [(str(workspace.id), str(form.form_id))]


# -------------------------------------------------------------------- the marker


async def test_staff_see_the_mark_and_a_submission_cannot_claim_it(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    done = await import_all(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"]]))
    imported = (await stored_answers(workspace, form))[0]
    shown = StandardFormResponseCamelModel(**imported.model_dump()).model_dump(by_alias=True, mode="json")
    assert shown["csvImportId"] == done["id"]
    forged = await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={"name": {"type": "text", "text": "Mallory"}}, csv_import_id=done["id"]
        ),
        testUser,
    )
    assert forged.csv_import_id is None
    # so an undo never reaches it
    await rollback(client, workspace, form, done["id"])
    assert await count(workspace, form) == 1


# -------------------------------------------------------------------- retention


async def set_retention(workspace, form, days):
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(workspace_id=workspace.id, query=str(form.form_id))
    link.settings.response_expiration_type = "days"
    link.settings.response_expiration = str(days)
    await repo.save_document(link)


async def test_the_forms_retention_runs_from_the_submission_time(client: AsyncClient, workspace, memory_jobs):
    form = await simple_form(workspace)
    await set_retention(workspace, form, 30)
    header = HEADER + ["Submitted at (UTC, ISO 8601)"]
    recent = (utcnow() - dt.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (utcnow() - dt.timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [header, ["Ada", "1", "Red", recent], ["Bob", "2", "Red", old]]
    refused = await import_all(client, workspace, form, csv_bytes(rows))
    # stored, Bob's would be deleted at once: refused instead
    assert refused["status"] == "failed" and refused["problems"] == [
        {"row": 3, "column": None, "code": "past_retention"}
    ]
    assert await count(workspace, form) == 0
    done = await import_all(client, workspace, form, csv_bytes(rows[:2]))
    assert done["status"] == "completed"
    stored = (await stored_answers(workspace, form))[0]
    assert stored.expiration and stored.expiration_type.value == "days"
    scheduled = [j for j in memory_jobs.jobs.values() if j["task_name"] == "delete_response"]
    assert len(scheduled) == 1


# ---------------------------------------------------------------- job robustness


async def test_a_job_that_runs_twice_stores_once(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    body = await import_all(client, workspace, form, csv_bytes(ROWS))
    assert body["status"] == "completed"
    assert await run_job(body["id"]) == "completed"
    assert await count(workspace, form) == 3


async def test_a_role_removed_before_the_job_runs_cancels_it(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    admin = await member(workspace, WorkspaceRoles.ADMIN)
    first = (await upload(client, workspace, form, csv_bytes(ROWS), user=admin)).json()
    queued = await post(
        client, workspace, form, first["id"], "/run",
        {"mapping": first["mapping"], "confirmedLawfulBasis": True}, user=admin,
    )
    assert queued.status_code == 202
    link = await container.workspace_user_repo().find_workspace_user(workspace.id, admin.id)
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save_document(link)
    assert await run_job(first["id"]) == "cancelled"
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.error_code == "permission_removed"
    assert await count(workspace, form) == 0
    assert await container.response_import_repo().count_files(first["id"]) == 0


async def test_a_worker_that_dies_half_way_leaves_nothing_after_the_retry(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], "confirmedLawfulBasis": True})
    repo = container.form_response_repo()
    real = repo.save_form_response
    calls = {"n": 0}

    async def dies(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise asyncio.CancelledError()  # the process is gone: nothing is cleaned up
        return await real(*args, **kwargs)

    monkeypatch.setattr(repo, "save_form_response", dies)
    with pytest.raises(asyncio.CancelledError):
        await run_job(first["id"])
    assert await count(workspace, form) == 2
    assert (await container.response_import_repo().get_by_id(first["id"])).status == ImportStatus.RUNNING
    monkeypatch.setattr(repo, "save_form_response", real)
    # the sweep finds it once its heartbeat is stale and queues it again
    later = utcnow() + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    swept = await service().redefer_pending()
    assert swept["queued"] == 1
    assert await run_job(first["id"]) == "completed"
    assert await count(workspace, form) == 3


async def test_a_job_that_keeps_dying_is_failed_and_undone(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], "confirmedLawfulBasis": True})
    repo = container.form_response_repo()
    real = repo.save_form_response
    calls = {"n": 0}

    async def dies(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise asyncio.CancelledError()
        return await real(*args, **kwargs)

    monkeypatch.setattr(repo, "save_form_response", dies)
    with pytest.raises(asyncio.CancelledError):
        await run_job(first["id"])
    monkeypatch.setattr(repo, "save_form_response", real)

    def worn_out(row):
        row.attempts = limits.MAX_ATTEMPTS
        return row

    await container.response_import_repo().update_locked(first["id"], worn_out)
    later = utcnow() + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().redefer_pending())["failed"] == 1
    row = await container.response_import_repo().get_by_id(first["id"])
    assert (row.status, row.error_code) == (ImportStatus.FAILED, "worker_lost")
    assert await count(workspace, form) == 0
    assert await container.response_import_repo().count_files(first["id"]) == 0


async def test_a_job_nobody_took_is_failed_after_its_maximum_age(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], "confirmedLawfulBasis": True})
    later = utcnow() + limits.QUEUED_MAX_AGE + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().redefer_pending())["failed"] == 1
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.error_code == "queue_timeout"
    assert await container.response_import_repo().count_files(first["id"]) == 0


# ----------------------------------------------------------------------- erasure


async def test_an_account_deleted_leaves_the_audit_row_without_it_and_no_file(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    waiting = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    done_form = await simple_form(workspace)
    done = await import_all(client, workspace, done_form, csv_bytes(ROWS))
    changed = await container.response_export_service().forget_actor(str(testUser.id))
    assert changed >= 2
    assert await container.response_import_repo().count_files(waiting["id"]) == 0
    repo = container.response_import_repo()
    for import_id in (waiting["id"], done["id"]):
        assert (await repo.get_by_id(import_id)).actor_id == DELETED_ACTOR
    assert (await repo.get_by_id(waiting["id"])).status == ImportStatus.DISCARDED
    assert (await repo.get_by_id(done["id"])).status == ImportStatus.COMPLETED


async def test_deleting_a_form_deletes_its_imports_and_files(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    waiting = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await container.response_export_service().delete_for_form(workspace.id, str(form.form_id))
    repo = container.response_import_repo()
    assert await repo.get_by_id(waiting["id"]) is None
    assert await repo.count_files(waiting["id"]) == 0


async def test_uploads_expire_and_their_files_with_them(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    later = utcnow() + limits.FILE_TTL + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    shown = await get(client, workspace, form, first["id"])
    assert shown.json()["status"] == "expired" and shown.json()["headers"] == []
    assert await container.response_import_repo().count_files(first["id"]) == 0
    refused = await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], "confirmedLawfulBasis": True})
    assert refused.status_code == 409


async def test_a_run_that_lost_its_claim_deletes_nothing_and_a_stray_row_fails_the_import(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], "confirmedLawfulBasis": True})
    repo = container.form_response_repo()
    real = repo.save_form_response
    seen = {"n": 0}

    async def stray(*args, **kwargs):
        seen["n"] += 1
        saved = await real(*args, **kwargs)
        if seen["n"] == 1:
            # a late write of an earlier run: one more row carrying this import's id
            other = dict(kwargs, response=kwargs["response"].model_copy(update={"response_id": str(RecordId())}))
            await real(*args, **other)
        return saved

    monkeypatch.setattr(repo, "save_form_response", stray)
    assert await run_job(first["id"]) == "failed"
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.error_code == "store_failed"
    assert await count(workspace, form) == 0


async def test_an_upload_with_no_import_row_is_swept(client: AsyncClient, workspace, monkeypatch):
    from backend.app.schemas.response_import import ResponseImportFileDocument

    repo = container.response_import_repo()
    lost = str(RecordId())
    await repo.save_file(
        ResponseImportFileDocument(import_id=lost, workspace_id=workspace.id, form_id="f", data="x")
    )
    assert await repo.count_files(lost) == 1
    later = utcnow() + limits.FILE_TTL + dt.timedelta(hours=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().purge_expired())["orphans"] == 1
    assert await repo.count_files(lost) == 0
