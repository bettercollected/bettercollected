"""A large export: the job, the encrypted file, the signed link, its expiry and
erasure."""

import base64
import datetime as dt
import json
import time

import pytest
from common.clock import utcnow
from common.records import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.response_export import ExportKind, ExportStatus
from backend.app.services.response_export import limits, links
from backend.app.services.response_export import service as service_module
from backend.app.services.response_export import writer
from tests.app.controllers.data import invited_user, testUser
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.response_export.helpers import (
    GROUP_FIELDS,
    answers,
    publish,
    rows,
    start,
    submit,
    submit_many,
    url,
    zip_rows,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def small_threshold(monkeypatch, memory_jobs):
    """Two responses already make a job; a chunk holds a few lines."""
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 2)
    monkeypatch.setattr(limits, "CHUNK_BYTES", 120)
    return memory_jobs


def service():
    return container.response_export_service()


def repo():
    return container.response_export_repo()


async def queued(client, workspace, form, body=None, user=testUser):
    response = await start(client, workspace, form, body, user=user)
    assert response.status_code == 202, response.text
    return response.json()


async def build(export_id):
    return await service().run_job(export_id)


async def status(client, workspace, form, export_id, user=testUser):
    return await client.get(url(workspace, form, f"/{export_id}"), cookies=_cookies(user))


async def fetch(client, workspace, form, export_id, user=testUser):
    """The ready export's file, through the link its status handed out."""
    ready = (await status(client, workspace, form, export_id, user)).json()
    if "downloadUrl" in ready:
        path = "/api/v1" + ready["downloadUrl"]
    else:
        # nothing to fetch any more: a freshly signed link meets the same answer
        token = links.issue(export_id, workspace.id, form.form_id, user.id)
        path = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/exports/{export_id}/download?token={token}"
    return await client.get(path, cookies=_cookies(user))


async def ready_export(client, workspace, form, count=5, body=None):
    await submit_many(workspace, form, count)
    queued_export = await queued(client, workspace, form, body)
    assert queued_export["status"] == "queued" and queued_export["kind"] == "job"
    assert await build(queued_export["id"]) == "ready"
    return queued_export["id"]


# --------------------------------------------------------------- the job itself


async def test_a_large_export_is_queued_built_and_downloaded_once(client: AsyncClient, workspace, small_threshold):
    form = await publish(workspace, hidden=["ref"])
    await submit_many(workspace, form, 5)
    first = await queued(client, workspace, form)
    assert first["rows"] == 5 and "downloadUrl" not in first
    # the job is queued by id only
    (job,) = small_threshold.jobs.values()
    assert job["task_name"] == "build_response_export" and job["args"] == {"export_id": first["id"]}
    assert job["queue_name"] == "default"

    pending = (await status(client, workspace, form, first["id"])).json()
    assert pending["status"] == "queued" and "downloadUrl" not in pending

    assert await build(first["id"]) == "ready"
    ready = (await status(client, workspace, form, first["id"])).json()
    assert ready["status"] == "ready" and ready["rows"] == 5 and ready["fileSize"] > 0
    assert ready["downloadUrl"].endswith(f"/exports/{first['id']}/download?token=" + ready["downloadUrl"].split("token=")[1])
    assert ready["linkExpiresInSeconds"] == limits_link_ttl()

    file = await fetch(client, workspace, form, first["id"])
    assert file.status_code == 200, file.text
    assert file.headers["content-type"].startswith("text/csv")
    assert file.headers["cache-control"] == "no-store"
    table = rows(file)
    assert table[0][:3] == ["Responder ID", "Full name", "Phone"] and len(table) == 6
    assert {r[1] for r in table[1:]} == {f"Person {n}" for n in range(5)}

    # fetched once: the file is gone, the audit entry stays
    entry = await repo().get_by_id(first["id"])
    assert entry.status == ExportStatus.DOWNLOADED and entry.downloaded_at and entry.file_deleted_at
    assert entry.kind == ExportKind.JOB and entry.row_count == 5 and entry.params_sealed is None
    assert await repo().count_chunks(first["id"]) == 0
    again = await fetch(client, workspace, form, first["id"])
    assert again.status_code == 410 and again.json()["code"] == "export_gone"


def limits_link_ttl():
    return links.LINK_TTL_SECONDS


async def test_the_job_file_equals_the_streamed_file(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form, count=4)
    from_job = (await fetch(client, workspace, form, export_id)).content
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 100)
    streamed = (await start(client, workspace, form)).content
    # the same columns and rows: both read the same stored responses
    assert from_job == streamed


async def test_a_group_form_job_builds_a_zip(client: AsyncClient, workspace):
    form = await publish(workspace, fields=GROUP_FIELDS)
    for number in range(3):
        given = answers(f"P{number}")
        given["jobs"] = {"type": "group", "items": [{"employer": {"type": "text", "text": f"E{number}"}}]}
        await submit(workspace, form, given)
    export = await queued(client, workspace, form)
    assert export["format"] == "zip" and export["fileName"] == "Export test.zip"
    assert await build(export["id"]) == "ready"
    file = await fetch(client, workspace, form, export["id"])
    assert file.headers["content-type"] == "application/zip"
    files = zip_rows(file.content)
    assert len(files["Export test - Jobs.csv"]) == 4


async def test_the_file_is_stored_encrypted_in_chunks_bound_to_the_export(client: AsyncClient, workspace):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    entry = await repo().get_by_id(export_id)
    assert entry.chunk_count > 3
    chunks = [await repo().get_chunk(export_id, i) for i in range(entry.chunk_count)]
    stored = json.dumps([c.model_dump(mode="json") for c in chunks])
    for secret in ("Person 1", "Full name", "Responder ID", "test@email.com"):
        assert secret not in stored
        assert secret.encode() not in b"".join(base64.b64decode(c.data) for c in chunks)
    # a chunk opens only as itself, for this export and this requester
    export = await repo().get_by_id(export_id)
    raw = base64.b64decode(chunks[0].data)
    service()._decrypt_chunk(export, 0, raw)
    from common.services.keyset import UnreadableCiphertext

    with pytest.raises(UnreadableCiphertext):
        service()._decrypt_chunk(export, 1, raw)
    other = export.model_copy(update={"id": RecordId()})
    with pytest.raises(UnreadableCiphertext):
        service()._decrypt_chunk(other, 0, raw)
    someone_else = export.model_copy(update={"actor_id": invited_user.id})
    with pytest.raises(UnreadableCiphertext):
        service()._decrypt_chunk(someone_else, 0, raw)
    # another workspace's key context
    foreign = export.model_copy(update={"workspace_id": RecordId()})
    with pytest.raises(UnreadableCiphertext):
        service()._decrypt_chunk(foreign, 0, raw)


async def test_the_filters_wait_sealed_and_are_gone_when_the_job_ends(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form, {"search": "test@email"})
    entry = await repo().get_by_id(export["id"])
    assert entry.params_sealed and "test@email" not in entry.params_sealed
    assert "test@email" not in base64.b64decode(entry.params_sealed).decode("latin-1")
    assert entry.filters == {"search": True}
    assert await build(export["id"]) == "ready"
    entry = await repo().get_by_id(export["id"])
    assert entry.params_sealed is None and entry.row_count == 3


async def test_the_job_honours_filters_and_columns(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 4)
    export = await queued(client, workspace, form, {"columns": ["q:name"], "search": "test@email"})
    await build(export["id"])
    file = await fetch(client, workspace, form, export["id"])
    table = rows(file)
    assert table[0] == ["Full name"] and len(table) == 5


async def test_a_second_job_waits_for_the_first(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    first = await queued(client, workspace, form)
    refused = await start(client, workspace, form)
    assert refused.status_code == 409 and refused.json()["code"] == "export_in_progress"
    # another user may ask meanwhile, and once the first is built so may they
    assert (await start(client, workspace, form, user=invited_user)).status_code == 202
    await build(first["id"])
    assert (await start(client, workspace, form)).status_code == 202


async def test_a_failed_build_is_marked_and_leaves_no_file(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 4)
    export = await queued(client, workspace, form)

    real = service_module.write_export

    async def broken(*args, **kwargs):
        count = 0
        async for piece in real(*args, **kwargs):
            yield piece
            count += 1
            if count == 2:
                raise RuntimeError("Person 1 could not be written")

    monkeypatch.setattr(writer, "PIECE_BYTES", 20)
    monkeypatch.setattr(service_module, "write_export", broken)
    assert await build(export["id"]) == "failed"
    entry = await repo().get_by_id(export["id"])
    assert entry.status == ExportStatus.FAILED and entry.error_code == "build_failed"
    assert entry.params_sealed is None and "Person" not in json.dumps(entry.model_dump(mode="json"))
    assert await repo().count_chunks(export["id"]) == 0
    seen = (await status(client, workspace, form, export["id"])).json()
    assert seen["status"] == "failed" and "downloadUrl" not in seen


async def test_a_file_that_would_be_too_large_fails_the_export(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 4)
    export = await queued(client, workspace, form)
    monkeypatch.setattr(limits, "MAX_FILE_BYTES", 200)
    assert await build(export["id"]) == "failed"
    entry = await repo().get_by_id(export["id"])
    assert entry.error_code == "too_large" and await repo().count_chunks(export["id"]) == 0


async def test_running_a_finished_export_again_does_nothing(client: AsyncClient, workspace):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    before = await repo().get_by_id(export_id)
    assert await build(export_id) == "ready"
    after = await repo().get_by_id(export_id)
    assert after.attempts == before.attempts == 1
    assert await build("0" * 24) == "missing"


# ------------------------------------------------------------------ the link


async def test_a_tampered_link_is_refused(client: AsyncClient, workspace):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    ready = (await status(client, workspace, form, export_id)).json()
    path = "/api/v1" + ready["downloadUrl"]
    expiry, _, signature = ready["downloadUrl"].split("token=")[1].partition(".")
    bad = [
        f"{expiry}.{'0' * len(signature)}",
        f"{expiry}.{signature[:-1]}{'0' if signature[-1] != '0' else '1'}",
        f"{int(expiry) + 3600}.{signature}",  # a longer life, same signature
        f"{expiry}",
        "garbage",
        ".",
        f"٣.{signature}",
    ]
    base = path.split("token=")[0]
    for token in bad:
        response = await client.get(base + "token=" + token, cookies=_cookies(testUser))
        assert response.status_code == 403, (token, response.text)
        assert response.json()["code"] == "invalid_link"
    assert (await client.get(base, cookies=_cookies(testUser))).status_code == 422
    # still downloadable with the real one: nothing above used it up
    assert (await client.get(path, cookies=_cookies(testUser))).status_code == 200


async def test_an_expired_link_is_refused_and_a_new_one_works(client: AsyncClient, workspace):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    entry = await repo().get_by_id(export_id)
    old = links.issue(entry.id, workspace.id, form.form_id, testUser.id, now=time.time() - links.LINK_TTL_SECONDS - 5)
    base = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/exports/{export_id}/download?token="
    response = await client.get(base + old, cookies=_cookies(testUser))
    assert response.status_code == 410 and response.json()["code"] == "link_expired"
    assert (await fetch(client, workspace, form, export_id)).status_code == 200


async def test_a_link_belongs_to_one_export_and_one_user(client: AsyncClient, workspace):
    form = await publish(workspace)
    first = await ready_export(client, workspace, form)
    second_export = await queued(client, workspace, form)
    await build(second_export["id"])
    link_of_first = (await status(client, workspace, form, first)).json()["downloadUrl"]
    token_of_first = link_of_first.split("token=")[1]
    base = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/exports/"
    # the first export's link on the second export
    cross = await client.get(f"{base}{second_export['id']}/download?token={token_of_first}", cookies=_cookies(testUser))
    assert cross.status_code == 403
    # a link made for another user on this user's export
    entry = await repo().get_by_id(first)
    for_other = links.issue(entry.id, workspace.id, form.form_id, invited_user.id)
    assert (await client.get(f"{base}{first}/download?token={for_other}", cookies=_cookies(testUser))).status_code == 403
    # another member signed in with the real link: not theirs, so not found
    await_member = await client.get("/api/v1" + link_of_first, cookies=_cookies(invited_user))
    assert await_member.status_code == 404
    # signed out
    assert (await client.get("/api/v1" + link_of_first)).status_code == 401
    # and the export is intact for its owner
    assert (await client.get("/api/v1" + link_of_first, cookies=_cookies(testUser))).status_code == 200


async def test_the_status_and_the_list_are_the_requesters_alone(client: AsyncClient, workspace):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    other = await status(client, workspace, form, export_id, user=invited_user)
    assert other.status_code == 404 and "Person" not in other.text
    mine = (await client.get(url(workspace, form), cookies=_cookies(testUser))).json()
    assert [e["id"] for e in mine] == [export_id] and mine[0]["status"] == "ready"
    theirs = (await client.get(url(workspace, form), cookies=_cookies(invited_user))).json()
    assert theirs == []
    # an export that does not exist is not found
    assert (await status(client, workspace, form, "0" * 24)).status_code == 404


async def test_one_download_at_a_time_and_a_broken_one_can_be_retried(workspace, client: AsyncClient):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    ready = (await status(client, workspace, form, export_id)).json()
    token = ready["downloadUrl"].split("token=")[1]
    claimed, body = await service().download(workspace.id, form.form_id, export_id, token, testUser)
    first = await body.__anext__()
    assert first
    from backend.app.exceptions import HTTPException

    with pytest.raises(HTTPException) as busy:
        await service().download(workspace.id, form.form_id, export_id, token, testUser)
    assert busy.value.status_code == 409
    # the reader goes away: the file stays and may be fetched again
    await body.aclose()
    entry = await repo().get_by_id(export_id)
    assert entry.status == ExportStatus.READY and entry.download_started_at is None
    assert (await fetch(client, workspace, form, export_id)).status_code == 200


# --------------------------------------------------------- permission changes


async def test_a_role_removed_before_the_job_runs_cancels_it(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form, user=invited_user)
    await container.workspace_user_repo().delete_where(
        container.workspace_user_repo().row.user_id == invited_user.id
    )
    assert await build(export["id"]) == "cancelled"
    entry = await repo().get_by_id(export["id"])
    assert entry.error_code == "permission_removed" and await repo().count_chunks(export["id"]) == 0


async def test_a_role_changed_after_the_file_is_ready_cannot_fetch_it(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form, user=invited_user)
    await build(export["id"])
    ready = (await status(client, workspace, form, export["id"], user=invited_user)).json()
    members = container.workspace_user_repo()
    member = await members.one(members.row.user_id == invited_user.id, members.row.workspace_id == str(workspace.id))
    member.roles = [WorkspaceRoles.PRIVACY_OFFICER]
    await members.save_document(member)
    refused = await client.get("/api/v1" + ready["downloadUrl"], cookies=_cookies(invited_user))
    assert refused.status_code == 403
    assert (await status(client, workspace, form, export["id"], user=invited_user)).status_code == 403


# ----------------------------------------------------------- erasure and expiry


async def test_a_response_deleted_before_the_job_runs_is_not_in_the_file(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 4)
    export = await queued(client, workspace, form)
    victim = sorted(await container.form_response_repo().many(), key=lambda r: str(r.id))[1]
    await container.form_response_service().delete_form_response(form.form_id, victim.response_id, workspace.id)
    assert await build(export["id"]) == "ready"
    names = {r[1] for r in rows(await fetch(client, workspace, form, export["id"]))[1:]}
    assert names == {"Person 0", "Person 2", "Person 3"}
    entry = await repo().get_by_id(export["id"])
    assert entry.expected_rows == 4 and entry.row_count == 3


async def test_a_deletion_removes_the_files_already_built(client: AsyncClient, workspace):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    other_form = await publish(workspace)
    other_id = await ready_export(client, workspace, other_form)
    assert await repo().count_chunks(export_id) > 0
    victim = (await container.form_response_repo().many())[0]
    await container.form_response_service().delete_form_response(
        victim.form_id, victim.response_id, workspace.id
    )
    entry = await repo().get_by_id(export_id)
    assert entry.status == ExportStatus.ERASED and entry.file_deleted_at and entry.row_count == 5
    assert await repo().count_chunks(export_id) == 0
    gone = await fetch(client, workspace, form, export_id)
    assert gone.status_code == 410
    # the other form's file is not touched
    assert (await repo().get_by_id(other_id)).status == ExportStatus.READY


@pytest.mark.parametrize("how", ["responses_of_form", "workspace_form", "form_ids", "retention", "workspaces"])
async def test_every_way_responses_are_deleted_drops_the_files(client: AsyncClient, workspace, how):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    responses = container.form_response_service()
    victim = (await container.form_response_repo().many())[0]
    if how == "responses_of_form":
        await responses.delete_form_responses(form.form_id)
    elif how == "workspace_form":
        await responses.delete_workspace_form_responses(workspace.id, form.form_id)
    elif how == "form_ids":
        await responses.delete_form_responses_of_form_ids([form.form_id])
    elif how == "retention":
        await responses.delete_response(response_id=victim.response_id)
    else:
        await responses.delete_workspaces_form_responses([str(workspace.id)], form.form_id)
    assert (await repo().get_by_id(export_id)).status == ExportStatus.ERASED
    assert await repo().count_chunks(export_id) == 0


async def test_a_job_that_is_building_when_responses_are_deleted_throws_its_file_away(
    client: AsyncClient, workspace, monkeypatch
):
    form = await publish(workspace)
    await submit_many(workspace, form, 6)
    export = await queued(client, workspace, form)
    victim = (await container.form_response_repo().many())[0]
    real = service_module.write_export
    deleted = {"done": False}

    async def deleting(*args, **kwargs):
        count = 0
        async for piece in real(*args, **kwargs):
            yield piece
            count += 1
            if count == 2 and not deleted["done"]:
                deleted["done"] = True
                await container.form_response_service().delete_form_response(
                    form.form_id, victim.response_id, workspace.id
                )

    monkeypatch.setattr(writer, "PIECE_BYTES", 20)
    monkeypatch.setattr(service_module, "write_export", deleting)
    assert await build(export["id"]) == "cancelled"
    entry = await repo().get_by_id(export["id"])
    assert entry.error_code == "responses_deleted" and entry.invalidated_at
    assert await repo().count_chunks(export["id"]) == 0
    seen = (await status(client, workspace, form, export["id"])).json()
    assert seen["status"] == "cancelled" and "downloadUrl" not in seen


async def test_a_file_goes_at_its_time(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    entry = await repo().get_by_id(export_id)
    assert entry.expires_at - entry.finished_at == limits.FILE_TTL
    assert await service().purge_expired() == 0
    later = entry.expires_at + dt.timedelta(seconds=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    # the status already reports it gone, and a download is refused, before the sweep
    ready = await service().status(workspace.id, form.form_id, export_id, testUser)
    assert ready["status"] == "expired" and "downloadUrl" not in ready
    assert await repo().count_chunks(export_id) == 0
    entry = await repo().get_by_id(export_id)
    assert entry.status == ExportStatus.EXPIRED and entry.file_deleted_at


async def test_the_sweep_deletes_expired_files(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    fresh = await ready_export(client, workspace, await publish(workspace))
    entry = await repo().get_by_id(export_id)
    monkeypatch.setattr(service(), "_clock", lambda: entry.expires_at + dt.timedelta(seconds=1))
    assert await service().purge_expired() == 2
    assert await repo().count_chunks(export_id) == 0 and await repo().count_chunks(fresh) == 0
    assert (await repo().get_by_id(export_id)).status == ExportStatus.EXPIRED


async def test_an_expired_link_to_an_expired_file_says_gone(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    entry = await repo().get_by_id(export_id)
    token = links.issue(entry.id, workspace.id, form.form_id, testUser.id, now=time.time() + limits.FILE_TTL.total_seconds())
    monkeypatch.setattr(service(), "_clock", lambda: entry.expires_at + dt.timedelta(minutes=1))
    base = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/exports/{export_id}/download?token="
    response = await client.get(base + token, cookies=_cookies(testUser))
    assert response.status_code == 410 and response.json()["code"] == "export_gone"


# -------------------------------------------------------------------- sweeps


async def test_a_job_that_was_never_queued_is_queued_again(client: AsyncClient, workspace, small_threshold, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form)
    small_threshold.jobs.clear()
    assert await service().redefer_pending() == {"queued": 0, "rescued": 0, "failed": 0}
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.REDEFER_AFTER + dt.timedelta(seconds=5))
    assert (await service().redefer_pending())["queued"] == 1
    (job,) = small_threshold.jobs.values()
    assert job["args"] == {"export_id": export["id"]}
    # the queueing lock keeps a second deferral from doubling it
    await service().redefer_pending()
    assert len(small_threshold.jobs) == 1


async def test_a_worker_that_died_leaves_a_job_that_is_taken_up_again(client: AsyncClient, workspace, small_threshold, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form)
    await repo().update_locked(export["id"], service()._claim)
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.RUNNING
    # still fresh: left alone, and a second worker cannot take it
    assert (await service().redefer_pending())["rescued"] == 0
    assert await build(export["id"]) == "running"
    later = utcnow() + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().redefer_pending())["rescued"] == 1
    assert (await repo().get_by_id(export["id"])).status == ExportStatus.QUEUED
    assert await build(export["id"]) == "ready"


async def test_a_job_that_keeps_dying_fails(client: AsyncClient, workspace, small_threshold, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    export = await queued(client, workspace, form)
    monkeypatch.setattr(limits, "STALE_RUNNING_AFTER", dt.timedelta(seconds=0))
    for _ in range(limits.MAX_ATTEMPTS):
        await repo().update_locked(export["id"], service()._claim)
        await service().redefer_pending()
    entry = await repo().get_by_id(export["id"])
    assert entry.status == ExportStatus.FAILED and entry.error_code == "worker_lost"


# ------------------------------------------------------------------- deleting


async def test_deleting_a_form_deletes_its_exports_and_files(client: AsyncClient, workspace):
    form = await publish(workspace)
    export_id = await ready_export(client, workspace, form)
    kept = await publish(workspace)
    kept_id = await ready_export(client, workspace, kept)
    await service().delete_for_form(workspace.id, form.form_id)
    assert await repo().get_by_id(export_id) is None and await repo().count_chunks(export_id) == 0
    assert (await repo().get_by_id(kept_id)).status == ExportStatus.READY
    await service().delete_for_workspaces([str(workspace.id)])
    assert await repo().many() == [] and await repo().count_chunks(kept_id) == 0
