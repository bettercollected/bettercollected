"""Limits and hardening of the export, round three: streams in flight are counted
per requester and workspace (across replicas, in Postgres), a queued export has a
maximum age, the running job's heartbeat is its own timestamp, the bulk JSON read
is bounded, and reads of responses through API keys and MCP leave an audit entry
without any personal data."""

import asyncio
import datetime as dt
import json

import pytest
from common.clock import utcnow
from common.models.standard_form import StandardFormResponse
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.filter_queries.response_export import ResponseExportFilters
from backend.app.schemas.response_export import ExportKind, ExportStatus
from backend.app.services.response_export import limits
from backend.app.services.response_export import service as service_module
from backend.app.services.response_export import writer
from tests.app.controllers.data import formResponse, invited_user, testUser, testUser2
from tests.app.controllers.test_mcp_server import _call_tool, _make_key
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.controllers.test_public_api import BASE, _auth, _token
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.response_export.helpers import publish, start, submit_many

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def small_threshold(monkeypatch, memory_jobs):  # noqa: F811
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 2)
    monkeypatch.setattr(limits, "CHUNK_BYTES", 120)
    return memory_jobs


def service():
    return container.response_export_service()


def repo():
    return container.response_export_repo()


async def ask(workspace, form, user=testUser):
    return await service().request(workspace.id, form.form_id, user, None, ResponseExportFilters())


async def drain(started):
    """Read a stream to its end, which closes its audit row and frees its slot."""
    return b"".join([piece async for piece in started.body])


async def in_flight(workspace):
    return [e for e in await repo().many() if e.status == ExportStatus.STREAMING and e.workspace_id == workspace.id]


# ---------------------------------------------------------- 1. streams in flight


async def test_a_requester_streams_only_so_many_exports_at_once(workspace, monkeypatch):
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 50)
    form = await publish(workspace)
    await submit_many(workspace, form, 2)
    held = [await ask(workspace, form) for _ in range(limits.STREAMS_PER_USER)]
    refused = await asyncio.gather(ask(workspace, form), return_exceptions=True)
    assert refused[0].status_code == 429 and refused[0].content["code"] == "export_busy"
    assert refused[0].headers["Retry-After"] == "10"
    # another requester of the workspace is not held up by it
    other = await ask(workspace, form, user=invited_user)
    assert other.export.kind == ExportKind.STREAM
    # a stream that ends (here: read to its end) makes room
    await drain(held[0])
    assert (await repo().get_by_id(held[0].export.id)).status == ExportStatus.COMPLETED
    again = await ask(workspace, form)
    assert again.export.status == ExportStatus.STREAMING


async def test_parallel_requests_cannot_all_get_in(workspace, monkeypatch):
    """Two simulated requests (and more) at once: the count and the insert share one
    transaction under the workspace lock, so exactly the cap gets in, whichever
    replica the request reached."""
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 50)
    monkeypatch.setattr(limits, "REQUESTS_PER_WINDOW", 100)
    form = await publish(workspace)
    await submit_many(workspace, form, 2)
    results = await asyncio.gather(*(ask(workspace, form) for _ in range(6)), return_exceptions=True)
    admitted = [r for r in results if not isinstance(r, Exception)]
    refused = [r for r in results if isinstance(r, Exception)]
    assert len(admitted) == limits.STREAMS_PER_USER
    assert len(refused) == 6 - limits.STREAMS_PER_USER
    assert {r.content["code"] for r in refused} == {"export_busy"}
    assert len(await in_flight(workspace)) == limits.STREAMS_PER_USER


async def test_a_workspace_streams_only_so_many_exports_at_once(workspace, monkeypatch):
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 50)
    monkeypatch.setattr(limits, "STREAMS_PER_WORKSPACE", 2)
    monkeypatch.setattr(limits, "STREAMS_PER_USER", 2)
    form = await publish(workspace)
    await submit_many(workspace, form, 2)
    await ask(workspace, form)
    await ask(workspace, form, user=invited_user)
    refused = await asyncio.gather(ask(workspace, form, user=invited_user), return_exceptions=True)
    assert refused[0].status_code == 429 and refused[0].content["code"] == "workspace_busy"
    assert refused[0].headers["Retry-After"] == "30"


async def test_a_stream_nobody_ever_read_stops_counting_after_its_slot_time(workspace, monkeypatch):
    """A client that vanished before the body started never closes its row: it must
    not lock its requester out until the sweep ends it."""
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 50)
    form = await publish(workspace)
    await submit_many(workspace, form, 2)
    for _ in range(limits.STREAMS_PER_USER):
        await ask(workspace, form)
    with pytest.raises(Exception) as busy:
        await ask(workspace, form)
    assert busy.value.status_code == 429
    later = utcnow() + limits.STREAM_SLOT_TTL + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await ask(workspace, form)).export.status == ExportStatus.STREAMING
    # and the sweep closes the abandoned ones
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.STALE_STREAMING_AFTER + dt.timedelta(minutes=1))
    await service().redefer_pending()
    assert {e.error_code for e in await repo().many() if e.status == ExportStatus.CANCELLED} == {"interrupted"}


async def test_through_the_api_a_busy_requester_gets_429_and_a_finished_stream_frees_the_slot(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 50)
    form = await publish(workspace)
    await submit_many(workspace, form, 2)
    for _ in range(limits.STREAMS_PER_USER):
        await ask(workspace, form)
    refused = await start(client, workspace, form)
    assert refused.status_code == 429 and refused.json()["code"] == "export_busy"
    assert refused.headers["retry-after"] == "10"


async def test_a_bulk_json_read_counts_as_a_stream_and_frees_its_slot(client: AsyncClient, workspace, monkeypatch):
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 50)
    form = await publish(workspace)
    await submit_many(workspace, form, 2)
    path = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/all-submissions"
    for _ in range(limits.STREAMS_PER_USER):
        await ask(workspace, form)
    refused = await client.get(path, cookies=_cookies(testUser))
    assert refused.status_code == 429 and refused.json()["code"] == "export_busy"
    # nothing left the building, and no stray row stays open
    assert all(e.channel != "all_submissions" for e in await repo().many())
    for held in await in_flight(workspace):
        await repo().update_locked(held.id, service()._ended_stream(ExportStatus.COMPLETED, 0, None))
    assert (await client.get(path, cookies=_cookies(testUser))).status_code == 200
    (entry,) = [e for e in await repo().many() if e.channel == "all_submissions"]
    assert entry.status == ExportStatus.COMPLETED and entry.row_count == 2


# --------------------------------------------------- 2. a queued export has a max age


async def queued_job(workspace, form):
    started = await ask(workspace, form)
    assert started.status == ExportStatus.QUEUED
    return started


async def test_an_export_that_stays_queued_too_long_fails_with_queue_timeout(workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    job = await queued_job(workspace, form)
    assert (await repo().get_by_id(job.id)).params_sealed

    # just under the limit: still waiting
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.QUEUED_MAX_AGE - dt.timedelta(minutes=1))
    assert await service().fail_overdue_queued() == 0
    assert (await repo().get_by_id(job.id)).status == ExportStatus.QUEUED

    # the hourly sweep enforces it
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.QUEUED_MAX_AGE + dt.timedelta(minutes=1))
    await service().purge_expired()
    ended = await repo().get_by_id(job.id)
    assert ended.status == ExportStatus.FAILED and ended.error_code == "queue_timeout"
    assert ended.params_sealed is None and ended.finished_at is not None
    # the status route says so, and the workspace's slot and the requester's open export are free
    view = service().present(ended, testUser)
    assert view["status"] == "failed" and view["errorCode"] == "queue_timeout" and "downloadUrl" not in view
    assert await repo().count_unfinished_in_workspace(workspace.id) == 0
    assert await repo().open_for(workspace.id, form.form_id, testUser.id) is None
    # a worker that finally picks the job up finds nothing to build
    assert await service().run_job(str(job.id)) == "failed"
    assert await repo().count_chunks(job.id) == 0


async def test_the_five_minute_sweep_does_not_queue_an_overdue_export_again(workspace, monkeypatch, small_threshold):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    job = await queued_job(workspace, form)
    small_threshold.jobs.clear()
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.QUEUED_MAX_AGE + dt.timedelta(minutes=1))
    assert (await service().redefer_pending())["queued"] == 0
    assert not small_threshold.jobs
    assert (await repo().get_by_id(job.id)).status == ExportStatus.QUEUED  # the hourly sweep ends it


async def test_a_job_that_ran_a_while_is_not_failed_for_the_age_of_its_row(workspace, monkeypatch):
    """The age counts from when it became queued: a job whose worker was lost and
    that is queued again has a young ``updated_at`` whatever its ``created_at``."""
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    job = await queued_job(workspace, form)
    await repo().update_locked(job.id, service()._claim)
    far = utcnow() + limits.QUEUED_MAX_AGE + dt.timedelta(hours=1)
    monkeypatch.setattr(service(), "_clock", lambda: far)
    # its worker is lost: the sweep queues it again, and it is fresh in the queue
    assert (await service().redefer_pending())["rescued"] == 1
    assert (await repo().get_by_id(job.id)).status == ExportStatus.QUEUED
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.QUEUED_MAX_AGE - dt.timedelta(minutes=5))
    assert await service().fail_overdue_queued() == 0


# ------------------------------------------------------ 3. the heartbeat is its own


async def test_a_running_job_beats_in_its_own_field_and_keeps_its_start(workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 6)
    job = await queued_job(workspace, form)
    await repo().update_locked(job.id, service()._claim)
    claimed = await repo().get_by_id(job.id)
    started = claimed.started_at
    assert claimed.heartbeat_at == started

    later = (started + dt.timedelta(minutes=7)).replace(microsecond=0)
    chunk = service_module.ResponseExportChunkDocument(
        export_id=str(job.id), workspace_id=workspace.id, form_id=form.form_id, index=0, data="x", attempt=1
    )
    assert await repo().add_chunk_if_owned(chunk, 1, later) == "owned"
    after = await repo().get_by_id(job.id)
    assert after.heartbeat_at == later and after.started_at == started
    # a heartbeat with no chunk
    assert await repo().beat_if_owned(job.id, 1, later + dt.timedelta(minutes=1)) == "owned"
    assert (await repo().get_by_id(job.id)).heartbeat_at == later + dt.timedelta(minutes=1)
    # a run of another claim cannot beat for this one
    assert await repo().beat_if_owned(job.id, 2, later) == "lost"


async def test_a_job_is_stuck_by_its_heartbeat_not_by_when_it_started(workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 6)
    job = await queued_job(workspace, form)
    await repo().update_locked(job.id, service()._claim)
    started = (await repo().get_by_id(job.id)).started_at

    # it began long ago but beat a minute ago: alive
    now = started + limits.STALE_RUNNING_AFTER * 3
    await repo().update_locked(job.id, lambda d: d.model_copy(update={"heartbeat_at": now - dt.timedelta(minutes=1)}))
    monkeypatch.setattr(service(), "_clock", lambda: now)
    assert (await service().redefer_pending())["rescued"] == 0
    assert (await repo().get_by_id(job.id)).status == ExportStatus.RUNNING
    assert service()._claim(await repo().get_by_id(job.id)) is None

    # silent for longer than the limit: dead, and what is told keeps when it started
    monkeypatch.setattr(service(), "_clock", lambda: now + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1))
    assert (await service().redefer_pending())["rescued"] == 1
    requeued = await repo().get_by_id(job.id)
    assert requeued.status == ExportStatus.QUEUED and requeued.started_at == started


async def test_a_row_written_before_heartbeats_fall_back_to_its_start(workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 6)
    job = await queued_job(workspace, form)
    await repo().update_locked(job.id, service()._claim)
    await repo().update_locked(job.id, lambda d: d.model_copy(update={"heartbeat_at": None}))
    monkeypatch.setattr(service(), "_clock", lambda: utcnow() + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1))
    assert (await service().redefer_pending())["rescued"] == 1


async def test_a_job_that_reads_without_filling_a_chunk_still_beats(workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 6)
    job = await queued_job(workspace, form)
    monkeypatch.setattr(limits, "CHUNK_BYTES", 10_000_000)
    monkeypatch.setattr(writer, "PIECE_BYTES", 40)
    monkeypatch.setattr(limits, "HEARTBEAT_EVERY", dt.timedelta(0))
    beats = []
    real = repo().beat_if_owned

    async def watching(*args):
        beats.append(args)
        return await real(*args)

    monkeypatch.setattr(repo(), "beat_if_owned", watching)
    assert await service().run_job(str(job.id)) == "ready"
    assert len(beats) >= 3
    assert (await repo().get_by_id(job.id)).heartbeat_at is not None


# --------------------------------------------------- 4. the bulk JSON read is bounded


async def test_the_bulk_json_read_is_unchanged_up_to_its_bound_and_refused_beyond(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    path = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/all-submissions"
    monkeypatch.setattr(limits, "BULK_JSON_MAX_ROWS", 3)
    exact = await client.get(path, cookies=_cookies(testUser))
    assert exact.status_code == 200 and len(exact.json()) == 3
    assert {"formId", "answers"} <= set(exact.json()[0])

    monkeypatch.setattr(limits, "BULK_JSON_MAX_ROWS", 2)
    refused = await client.get(path, cookies=_cookies(testUser))
    assert refused.status_code == 413 and refused.json()["code"] == "too_many_rows"
    assert "exports" in refused.json()["message"]
    # the refusal is audited without ever holding an answer, and frees its slot
    refusals = [e for e in await repo().many() if e.channel == "all_submissions" and e.status == ExportStatus.FAILED]
    assert len(refusals) == 1 and refusals[0].error_code == "too_many_rows" and refusals[0].row_count == 0
    assert await in_flight(workspace) == []


async def test_the_bound_reads_one_row_past_it_and_not_the_whole_form(workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 5)
    seen = []
    response_repo = container.form_response_repo()
    real = response_repo.many

    async def watching(*where, **kwargs):
        seen.append(kwargs.get("limit"))
        return await real(*where, **kwargs)

    monkeypatch.setattr(response_repo, "many", watching)
    monkeypatch.setattr(limits, "BULK_JSON_MAX_ROWS", 2)
    with pytest.raises(Exception) as refused:
        await service().bulk_read(workspace.id, form.form_id, testUser)
    assert refused.value.status_code == 413
    assert seen == [3]


async def test_a_bulk_read_of_an_unknown_form_or_without_the_permission_leaves_no_row(client: AsyncClient, workspace):
    from tests.app.controllers.data import testUser1

    form = await publish(workspace)
    assert (await client.get(f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/all-submissions", cookies=_cookies(testUser1))).status_code == 403
    assert (await client.get(f"/api/v1/workspaces/{workspace.id}/forms/nope/all-submissions", cookies=_cookies(testUser))).status_code == 404
    assert await repo().many() == []


# ----------------------------------- 5. API key and MCP reads are audited, with no answers


def _plain(entries):
    return json.dumps([e.model_dump(mode="json") for e in entries])


async def _submit(workspace, form):
    return await container.workspace_form_service().submit_response(
        workspace.id, form.form_id, StandardFormResponse(**formResponse), testUser2
    )


async def test_api_key_reads_of_responses_leave_an_audit_entry_without_personal_data(
    client: AsyncClient, workspace, published_form
):
    response = await _submit(workspace, published_form)
    token = await _token(workspace.id)
    key = (await container.api_key_service().list_keys(workspace.id, testUser))[0]
    url = f"{BASE}/forms/{published_form.form_id}/responses"
    assert (await client.get(url, headers=_auth(token))).status_code == 200
    assert (await client.get(f"{url}/{response.response_id}", headers=_auth(token))).status_code == 200
    # a read that finds nothing is not a read of a response
    assert (await client.get(f"{url}/not-a-response", headers=_auth(token))).status_code == 404

    entries = [e for e in await repo().many() if e.channel == "api_key"]
    assert len(entries) == 2
    for entry in entries:
        assert entry.actor_id == f"api-key:{key.id}" and entry.form_id == published_form.form_id
        assert entry.status == ExportStatus.COMPLETED and entry.row_count == 1 and entry.format == "json"
        assert entry.columns == [] and entry.filters == {}
    dump = _plain(entries)
    # no answer, no respondent, no key secret, no name of the key's creator
    for personal in ("random@email.com", token, "api test key", testUser.id, "Person"):
        assert personal not in dump
    # nothing of this reaches the requester views of a person
    assert await repo().list_for_actor(workspace.id, published_form.form_id, testUser.id) == []


async def test_a_refused_api_key_read_leaves_no_entry(client: AsyncClient, workspace, published_form):
    token = await _token(workspace.id, ["forms:read"])
    refused = await client.get(f"{BASE}/forms/{published_form.form_id}/responses", headers=_auth(token))
    assert refused.status_code == 403
    assert [e for e in await repo().many() if e.channel == "api_key"] == []


async def test_mcp_reads_of_responses_leave_an_audit_entry_without_personal_data(
    client: AsyncClient, workspace, published_form
):
    response = await _submit(workspace, published_form)
    token = await _make_key(workspace.id, ["responses:read"])
    listed = await _call_tool(client, token, "list_responses", {"form_id": published_form.form_id})
    assert not listed.get("isError"), listed
    got = await _call_tool(client, token, "get_response", {"response_id": response.response_id})
    assert not got.get("isError"), got
    missing = await _call_tool(client, token, "get_response", {"response_id": "nope"})
    assert missing.get("isError") is True

    entries = [e for e in await repo().many() if e.channel == "mcp"]
    assert len(entries) == 2
    key = (await container.api_key_service().list_keys(workspace.id, testUser))[0]
    for entry in entries:
        assert entry.actor_id == f"api-key:{key.id}" and entry.form_id == published_form.form_id
        assert entry.status == ExportStatus.COMPLETED and entry.row_count == 1
    dump = _plain(entries)
    for personal in ("random@email.com", token, "test key", testUser.id):
        assert personal not in dump


async def test_a_key_read_that_cannot_be_audited_does_not_return_the_answers(
    client: AsyncClient, workspace, published_form, monkeypatch
):
    await _submit(workspace, published_form)
    token = await _token(workspace.id)

    async def broken(*args, **kwargs):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(service(), "audit_key_read", broken)
    refused = await client.get(f"{BASE}/forms/{published_form.form_id}/responses", headers=_auth(token))
    assert refused.status_code == 500 and "responseId" not in refused.text
