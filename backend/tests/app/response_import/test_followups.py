"""The follow-ups of the reviews: unused uploads expire from the 5-minute task,
a failed cleanup is tried again (by the sweep and by the undo), uploads are
limited per workspace, imports have their own queue."""

import datetime as dt

import pytest
from common.clock import utcnow
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.response_import import ImportStatus
from backend.app.services.response_import import limits
from backend.app.services.response_import.service import ResponseImportService
from tests.app.controllers.data import testUser
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.response_import.helpers import csv_bytes, get, post, publish_form, run_job, service, upload, url
from tests.app.response_import.test_flow import HEADER, SIMPLE, count, simple_form

pytestmark = pytest.mark.asyncio

ROWS = [HEADER, ["Ada", "36", "Red"], ["Bob", "40", "Blue"], ["Cy", "50", "Red"]]
RUN = {"confirmedLawfulBasis": True}


# ---------------------------------------------------- unused uploads, every 5 min


async def test_the_five_minute_task_deletes_unused_uploads_past_their_hour(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    waiting = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    imports = container.response_import_repo()
    expires = (await imports.get_by_id(waiting["id"])).expires_at
    # not yet: nothing is deleted before the hour
    assert (await service().redefer_pending())["expired"] == 0
    assert await imports.count_files(waiting["id"]) == 1
    later = expires + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().redefer_pending())["expired"] == 1
    assert (await imports.get_by_id(waiting["id"])).status == ImportStatus.EXPIRED
    assert await imports.count_files(waiting["id"]) == 0


async def test_a_checked_upload_past_its_hour_goes_too(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})
    assert await run_job(first["id"]) == "checked"
    imports = container.response_import_repo()
    later = (await imports.get_by_id(first["id"])).expires_at + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().redefer_pending())["expired"] == 1
    assert await imports.count_files(first["id"]) == 0


# ------------------------------------------------------------- a failed cleanup


async def _failed_with_stray_rows(client, workspace, form, monkeypatch):
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    repo = container.form_response_repo()
    real_save, real_delete = repo.save_form_response, repo.delete_imported
    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("the database went away")
        return await real_save(*args, **kwargs)

    async def broken(*args, **kwargs):
        raise RuntimeError("the delete failed too")

    monkeypatch.setattr(repo, "save_form_response", flaky)
    monkeypatch.setattr(repo, "delete_imported", broken)
    assert await run_job(first["id"]) == "failed"
    monkeypatch.setattr(repo, "save_form_response", real_save)
    monkeypatch.setattr(repo, "delete_imported", real_delete)
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.status == ImportStatus.FAILED and row.undo_pending is True
    assert await count(workspace, form) == 2
    return first["id"]


async def test_a_failed_cleanup_is_tried_again_by_the_sweep(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    import_id = await _failed_with_stray_rows(client, workspace, form, monkeypatch)
    assert (await service().redefer_pending())["undone"] == 1
    assert await count(workspace, form) == 0
    assert (await container.response_import_repo().get_by_id(import_id)).undo_pending is False
    # nothing left to do
    assert (await service().redefer_pending())["undone"] == 0


async def test_a_failed_cleanup_can_be_undone_by_hand(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    import_id = await _failed_with_stray_rows(client, workspace, form, monkeypatch)
    shown = (await get(client, workspace, form, import_id)).json()
    assert shown["status"] == "failed"
    done = await client.post(url(workspace, form, f"/{import_id}/rollback"), json={}, cookies=_cookies(testUser))
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "failed" and done.json()["rolledBackCount"] == 2
    assert await count(workspace, form) == 0
    # a failed import with nothing stray is still not an undo
    again = await client.post(url(workspace, form, f"/{import_id}/rollback"), json={}, cookies=_cookies(testUser))
    assert again.status_code == 409 and again.json()["code"] == "not_rollbackable"


async def test_the_failed_cleanup_is_marked_only_when_it_failed(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes([HEADER, ["Ada", "999", "Red"]]))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    await run_job(first["id"])
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.status == ImportStatus.FAILED and row.undo_pending is False


# --------------------------------------------------------- the workspace's limit


async def test_uploads_are_limited_per_workspace_too(client: AsyncClient, workspace, monkeypatch):
    monkeypatch.setattr(limits, "WORKSPACE_UPLOADS_PER_WINDOW", 2)
    one = await simple_form(workspace)
    two = await publish_form(workspace, SIMPLE, title="Second")
    three = await publish_form(workspace, SIMPLE, title="Third")
    data = csv_bytes(ROWS)
    assert (await upload(client, workspace, one, data)).status_code == 201
    assert (await upload(client, workspace, two, data)).status_code == 201
    limited = await upload(client, workspace, three, data)
    assert limited.status_code == 429 and limited.json()["code"] == "workspace_rate_limited"
    assert int(limited.headers["retry-after"]) > 0
    assert await container.response_import_repo().list_for_form(workspace.id, str(three.form_id)) == []


# ----------------------------------------------------------------- its own queue


async def test_imports_have_their_own_queue_that_the_worker_serves_by_default(client: AsyncClient, workspace, memory_jobs):
    from backend.jobs import tasks, worker
    from backend.jobs.app import EXPORTS_QUEUE, IMPORTS_QUEUE

    assert IMPORTS_QUEUE != EXPORTS_QUEUE
    assert tasks.run_response_import.queue == IMPORTS_QUEUE
    assert limits.IMPORTS_QUEUE == IMPORTS_QUEUE
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    queued = [job for job in memory_jobs.jobs.values() if job["task_name"] == "run_response_import"]
    assert [job["queue_name"] for job in queued] == [IMPORTS_QUEUE]
    # a worker told to serve other queues only says so at start
    assert worker.warn_if_imports_unserved(["default", "exports"]) is True
    assert worker.warn_if_imports_unserved(["default", IMPORTS_QUEUE]) is False


def test_the_context_names_the_import_only():
    assert ResponseImportService._context_bytes("abc") == b"import-file|abc"
