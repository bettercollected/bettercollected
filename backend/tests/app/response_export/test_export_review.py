"""Round two of the review of the export: two runs of one job never mix their
chunks, one live export per requester and form, a cap per workspace, the queue of
its own, the bulk JSON route audited like an export, and what an account's deletion
and a provider sync do to the audit rows and files."""

import asyncio
import datetime as dt
import json

import pytest
from common.clock import utcnow
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.filter_queries.response_export import ResponseExportFilters
from backend.app.schemas.response_export import DELETED_ACTOR, ExportStatus
from backend.app.services.response_export import limits, links
from backend.app.services.response_export import service as service_module
from backend.app.services.response_export import writer
from tests.app.controllers.data import invited_user, testUser
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.response_export.helpers import publish, rows, start, submit_many, url

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def small_threshold(monkeypatch, memory_jobs):  # noqa: F811
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 2)
    monkeypatch.setattr(limits, "CHUNK_BYTES", 120)
    monkeypatch.setattr(writer, "PIECE_BYTES", 40)
    return memory_jobs


def service():
    return container.response_export_service()


def repo():
    return container.response_export_repo()


async def queued(client, workspace, form, user=testUser, body=None):
    response = await start(client, workspace, form, body, user=user)
    assert response.status_code == 202, response.text
    return response.json()


async def ready_file(client, workspace, form, export_id, user=testUser):
    status = (await client.get(url(workspace, form, f"/{export_id}"), cookies=_cookies(user))).json()
    if "downloadUrl" in status:
        path = "/api/v1" + status["downloadUrl"]
    else:
        # nothing to fetch any more: a freshly signed link meets the same answer
        token = links.issue(export_id, workspace.id, form.form_id, user.id)
        path = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/exports/{export_id}/download?token={token}"
    return await client.get(path, cookies=_cookies(user))


async def discard(client, workspace, form, export_id, user=testUser):
    return await client.delete(url(workspace, form, f"/{export_id}"), cookies=_cookies(user))


# ----------------------------------------------------- two runs of one job


async def test_a_slow_run_that_was_swept_cannot_mix_its_chunks_into_the_file(client: AsyncClient, workspace, small_threshold, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 8)
    export = await queued(client, workspace, form)
    first_paused, release = asyncio.Event(), asyncio.Event()
    real = service_module.write_export
    state = {"runs": 0}

    async def gated(*args, **kwargs):
        state["runs"] += 1
        mine = state["runs"]
        count = 0
        async for piece in real(*args, **kwargs):
            yield piece
            count += 1
            if mine == 1 and count == 6:
                first_paused.set()
                await release.wait()

    monkeypatch.setattr(service_module, "write_export", gated)
    slow = asyncio.create_task(service().run_job(export["id"]))
    await first_paused.wait()
    mid = await repo().get_by_id(export["id"])
    assert mid.status == ExportStatus.RUNNING and mid.attempts == 1
    assert await repo().count_chunks(export["id"]) >= 1

    # nothing has heartbeated for longer than the limit: the sweep takes it for dead
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1))
    assert (await service().redefer_pending())["rescued"] == 1
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.QUEUED
    assert await repo().count_chunks(export["id"]) == 0

    # the second run builds the whole file while the first is still alive
    assert await service().run_job(export["id"]) == "ready"
    built = await repo().get_by_id(export["id"])
    assert built.attempts == 2 and built.chunk_count > 1
    chunks_before = [(await repo().get_chunk(export["id"], i)).data for i in range(built.chunk_count)]

    release.set()
    # the first run finds it has been superseded: it stores nothing, ends nothing
    assert await slow == "ready"
    after = await repo().get_by_id(export["id"])
    assert after.status == ExportStatus.READY and after.attempts == 2 and after.chunk_count == built.chunk_count
    chunks_after = [await repo().get_chunk(export["id"], i) for i in range(built.chunk_count)]
    assert [c.data for c in chunks_after] == chunks_before
    assert {c.attempt for c in chunks_after} == {2}
    assert await repo().count_chunks(export["id"]) == built.chunk_count
    monkeypatch.undo()
    file = await ready_file(client, workspace, form, export["id"])
    assert file.status_code == 200 and len(rows(file)) == 9


async def test_every_stored_chunk_is_a_heartbeat(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 6)
    export = await queued(client, workspace, form)
    stamps = []
    real = repo().add_chunk_if_owned

    async def watching(chunk, attempt, now):
        result = await real(chunk, attempt, now)
        stamps.append((await repo().get_by_id(export["id"])).started_at)
        return result

    monkeypatch.setattr(repo(), "add_chunk_if_owned", watching)
    ticks = iter(utcnow() + dt.timedelta(minutes=n) for n in range(1, 100))
    monkeypatch.setattr(service(), "_clock", lambda: next(ticks))
    assert await service().run_job(export["id"]) == "ready"
    assert len(stamps) > 2 and stamps == sorted(stamps) and len(set(stamps)) == len(stamps)


async def test_a_stale_run_cannot_end_the_export_either(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 4)
    export = await queued(client, workspace, form)
    claimed = await repo().update_locked(export["id"], service()._claim)
    assert claimed.attempts == 1
    # another claim takes over
    await repo().update_locked(export["id"], lambda d: d.model_copy(update={"status": ExportStatus.QUEUED}))
    again = await repo().update_locked(export["id"], service()._claim)
    assert again.attempts == 2
    assert await service()._end_owned(claimed, ExportStatus.FAILED, "build_failed") == ExportStatus.RUNNING
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.RUNNING


# ------------------------------------------------- storage and worker abuse


async def test_a_ready_file_blocks_a_new_export_until_it_is_deleted_or_expires(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    first = await queued(client, workspace, form)
    await service().run_job(first["id"])
    refused = await start(client, workspace, form)
    assert refused.status_code == 409 and refused.json()["code"] == "export_ready"
    # another requester, and another form, are not held up
    assert (await start(client, workspace, form, user=invited_user)).status_code == 202
    other = await publish(workspace)
    await submit_many(workspace, other, 3)
    assert (await start(client, workspace, other)).status_code == 202
    # downloading does not free it: only its requester's delete, or the 24 hours, do
    assert (await ready_file(client, workspace, form, first["id"])).status_code == 200
    assert (await start(client, workspace, form)).status_code == 409
    assert (await discard(client, workspace, form, first["id"])).status_code == 204
    assert (await start(client, workspace, form)).status_code == 202


async def test_two_requests_at_once_make_one_job(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    results = await asyncio.gather(
        service().request(workspace.id, form.form_id, testUser, None, ResponseExportFilters()),
        service().request(workspace.id, form.form_id, testUser, None, ResponseExportFilters()),
        return_exceptions=True,
    )
    refused = [r for r in results if isinstance(r, Exception)]
    assert len(refused) == 1 and refused[0].status_code == 409
    jobs = [e for e in await repo().many() if e.status == ExportStatus.QUEUED]
    assert len(jobs) == 1


async def test_a_workspace_runs_only_so_many_jobs_at_once(client: AsyncClient, workspace, monkeypatch):
    forms = []
    for _ in range(limits.WORKSPACE_MAX_JOBS + 1):
        form = await publish(workspace)
        await submit_many(workspace, form, 3)
        forms.append(form)
    for form in forms[: limits.WORKSPACE_MAX_JOBS]:
        assert (await start(client, workspace, form)).status_code == 202
    busy = await start(client, workspace, forms[-1])
    assert busy.status_code == 429 and busy.json()["code"] == "workspace_busy"
    assert busy.headers["retry-after"] == "60"
    # a job that ends makes room (a file waiting to be fetched is not running)
    (first,) = [e for e in await repo().many() if e.form_id == forms[0].form_id]
    await service().run_job(str(first.id))
    assert (await start(client, workspace, forms[-1])).status_code == 202


async def test_a_large_export_is_queued_on_its_own_queue(client: AsyncClient, workspace, small_threshold):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    await queued(client, workspace, form)
    (job,) = small_threshold.jobs.values()
    assert job["queue_name"] == "exports" and job["task_name"] == "build_response_export"


async def test_the_worker_warns_when_it_does_not_serve_the_exports_queue(caplog):
    from backend.jobs import worker

    assert worker.warn_if_exports_unserved(["default", "webhooks"]) is True
    assert worker.warn_if_exports_unserved(["default", "webhooks", "exports"]) is False
    assert worker.EXPORTS_QUEUE in {"default", "webhooks", "exports"}


# ------------------------------------------- the bulk JSON route is audited too


async def test_the_bulk_json_route_leaves_an_audit_entry_and_is_rate_limited(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    path = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/all-submissions"
    response = await client.get(path, cookies=_cookies(testUser))
    assert response.status_code == 200 and len(response.json()) == 3
    (entry,) = await repo().list_for_form(workspace.id, form.form_id)
    assert entry.channel == "all_submissions" and entry.actor_id == testUser.id
    assert entry.row_count == 3 and entry.status == ExportStatus.COMPLETED and entry.format == "json"
    assert "Person" not in json.dumps(entry.model_dump(mode="json"))
    # it shares the export's limit
    monkeypatch.setattr(limits, "REQUESTS_PER_WINDOW", 2)
    assert (await client.get(path, cookies=_cookies(testUser))).status_code == 200
    refused = await client.get(path, cookies=_cookies(testUser))
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) >= 1
    assert (await start(client, workspace, form)).status_code == 429


async def test_a_refused_bulk_read_leaves_no_entry(client: AsyncClient, workspace):
    from tests.app.controllers.data import testUser1

    form = await publish(workspace)
    path = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/all-submissions"
    assert (await client.get(path, cookies=_cookies(testUser1))).status_code == 403
    assert await repo().many() == []


# ------------------------------------------------ account deletion and the sync


async def test_a_deleted_account_leaves_its_audit_rows_without_the_user(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    mine = await queued(client, workspace, form, user=invited_user)
    await service().run_job(mine["id"])
    streamed = await start(client, workspace, form, user=invited_user)
    assert streamed.status_code in (200, 202, 409)
    other = await start(client, workspace, form)
    assert other.status_code in (200, 202)

    await container.workspace_service().forget_exports_of_user(invited_user.id)

    rows_after = await repo().many()
    assert rows_after and all(r.actor_id != invited_user.id for r in rows_after)
    assert invited_user.id not in json.dumps([r.model_dump(mode="json") for r in rows_after])
    gone = await repo().get_by_id(mine["id"])
    assert gone.actor_id == DELETED_ACTOR and gone.status == ExportStatus.ERASED and gone.row_count == 3
    assert await repo().count_chunks(mine["id"]) == 0
    # the other requester's rows are untouched
    assert any(r.actor_id == testUser.id for r in rows_after)
    # a second pass changes nothing
    assert await service().forget_actor(invited_user.id) == 0


async def test_a_job_of_a_deleted_account_does_not_run(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form, user=invited_user)
    await container.workspace_service().forget_exports_of_user(invited_user.id)
    assert await service().run_job(export["id"]) == "cancelled"
    assert await repo().count_chunks(export["id"]) == 0


async def test_account_deletion_calls_the_hook(monkeypatch):
    from unittest.mock import AsyncMock

    auth = container.auth_service()
    calls = []
    monkeypatch.setattr(auth.workspace_service, "refuse_deleting_billing_owner_of_shared_workspaces", AsyncMock())
    monkeypatch.setattr(auth.workspace_service, "delete_workspaces_of_user_with_forms", AsyncMock())
    monkeypatch.setattr(auth.workspace_service, "forget_exports_of_user", AsyncMock(side_effect=lambda uid: calls.append(uid)))
    monkeypatch.setattr(auth, "delete_user_form_auth", AsyncMock())
    monkeypatch.setattr(auth.session_service, "delete_all_for_user", AsyncMock())
    monkeypatch.setattr(auth, "delete_credentials_from_integrations", AsyncMock())
    await auth.delete_user(testUser)
    assert calls == [testUser.id]


async def test_a_provider_sync_that_deletes_nothing_keeps_the_files(client: AsyncClient, workspace):
    from tests.app.controllers.test_responses_per_workspace import FORM_ID, _import

    await _import(workspace, testUser, ["r1", "r2", "r3"], "synced")
    export = await queued_provider(client, workspace)
    assert await service().run_job(export["id"]) == "ready"
    # the same responses again: nothing was deleted, the file stays
    await _import(workspace, testUser, ["r1", "r2", "r3"], "synced")
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.READY
    assert await repo().count_chunks(export["id"]) > 0
    # a response the provider no longer has: the file goes
    await _import(workspace, testUser, ["r1", "r2"], "synced")
    gone = await repo().get_by_id(export["id"])
    assert gone.status == ExportStatus.ERASED and await repo().count_chunks(export["id"]) == 0
    assert FORM_ID


async def queued_provider(client, workspace):
    from tests.app.controllers.test_responses_per_workspace import FORM_ID

    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{FORM_ID}/exports", json={}, cookies=_cookies(testUser)
    )
    assert response.status_code == 202, response.text
    return response.json()


async def test_an_old_failure_is_no_longer_news(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form)
    monkeypatch.setattr(limits, "MAX_FILE_BYTES", 50)
    assert await service().run_job(export["id"]) == "failed"
    listed = (await client.get(url(workspace, form), cookies=_cookies(testUser))).json()
    assert [e["status"] for e in listed] == ["failed"]
    entry = await repo().get_by_id(export["id"])
    monkeypatch.setattr(service(), "_clock", lambda: entry.finished_at + limits.FAILURE_NEWS_FOR + dt.timedelta(minutes=1))
    assert await service().recent(workspace.id, form.form_id, testUser) == []
    # the audit row is still there
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.FAILED


# ----------------------------------------------------------- deleting a ready file


async def test_the_requester_deletes_a_ready_file_and_the_audit_entry_stays(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 4)
    export = await queued(client, workspace, form)
    await service().run_job(export["id"])
    assert (await ready_file(client, workspace, form, export["id"])).status_code == 200
    gone = await discard(client, workspace, form, export["id"])
    assert gone.status_code == 204 and gone.content == b"" and gone.headers["cache-control"] == "no-store"
    entry = await repo().get_by_id(export["id"])
    assert entry.status == ExportStatus.DISCARDED and entry.file_deleted_at and entry.expires_at is None
    assert entry.row_count == 4 and entry.download_count == 1 and entry.actor_id == testUser.id
    assert await repo().count_chunks(export["id"]) == 0
    refused = await ready_file(client, workspace, form, export["id"])
    assert refused.status_code == 410
    status = (await client.get(url(workspace, form, f"/{export['id']}"), cookies=_cookies(testUser))).json()
    assert status["status"] == "discarded" and "downloadUrl" not in status
    # deleting again is fine: it is already gone
    assert (await discard(client, workspace, form, export["id"])).status_code == 204
    # and a new export can be started
    assert (await start(client, workspace, form)).status_code == 202


async def test_only_the_requester_may_delete_a_file(client: AsyncClient, workspace):
    from tests.app.controllers.data import testUser1

    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form)
    await service().run_job(export["id"])
    other = await discard(client, workspace, form, export["id"], user=invited_user)
    assert other.status_code == 404
    assert (await discard(client, workspace, form, export["id"], user=testUser1)).status_code == 403
    assert (await client.delete(url(workspace, form, f"/{export['id']}"))).status_code == 401
    assert (await discard(client, workspace, form, "0" * 24)).status_code == 404
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.READY
    assert await repo().count_chunks(export["id"]) > 0


async def test_an_export_that_is_still_being_built_has_no_file_to_delete(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form)
    refused = await discard(client, workspace, form, export["id"])
    assert refused.status_code == 409 and refused.json()["code"] == "export_not_ready"
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.QUEUED


async def test_a_role_that_cannot_export_cannot_delete(client: AsyncClient, workspace):
    from backend.app.models.enum.workspace_roles import WorkspaceRoles
    from backend.app.schemas.workspace_user import WorkspaceUserDocument
    from common.models.user import User
    from common.records import RecordId

    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form)
    await service().run_job(export["id"])
    officer = User(id=str(RecordId()), sub="officer@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=officer.id, roles=[WorkspaceRoles.PRIVACY_OFFICER])
    )
    assert (await discard(client, workspace, form, export["id"], user=officer)).status_code == 403
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.READY
