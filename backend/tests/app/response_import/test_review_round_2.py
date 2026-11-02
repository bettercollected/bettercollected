"""The second review: no signatures from a cell, the file's hour is absolute,
the confirmer's permission runs the job."""

import asyncio
import datetime as dt

import pytest
from common.clock import utcnow
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.response_import import ImportStatus
from backend.app.services.response_import import limits
from backend.app.services.response_import.targets import STATUS_UNSUPPORTED, build_targets
from tests.app.controllers.data import testUser
from tests.app.response_import.helpers import (
    csv_bytes,
    get,
    post,
    publish_form,
    run_job,
    service,
    stored_answers,
    upload,
)
from tests.app.response_import.test_flow import HEADER, SIMPLE, count, member, simple_form

pytestmark = pytest.mark.asyncio

ROWS = [HEADER, ["Ada", "36", "Red"], ["Bob", "40", "Blue"], ["Cy", "50", "Red"]]
RUN = {"confirmedLawfulBasis": True}


# ------------------------------------------------------------------- signature


def test_a_signature_question_is_unsupported_for_import():
    form = {
        "builder_version": "v2",
        "title": "F",
        "fields": [
            {
                "id": "s1",
                "type": "slide",
                "index": 0,
                "properties": {"fields": [{"id": "sig", "type": "signature", "title": "Signature"}]},
            }
        ],
    }
    found = {t.key: t for t in build_targets(form)}
    assert (found["q:sig"].status, found["q:sig"].reason) == (STATUS_UNSUPPORTED, "signature_unsupported")


async def test_a_signature_column_is_left_out_with_a_note_and_never_mapped(client: AsyncClient, workspace):
    fields = SIMPLE + [{"id": "sig", "type": "signature", "title": "Signature"}]
    form = await publish_form(workspace, fields, title="Signed")
    first = (await upload(client, workspace, form, csv_bytes([HEADER + ["Signature"], ["Ada", "36", "Red", "A. Lovelace"]]))).json()
    assert "q:sig" not in first["mapping"].values()
    assert {"column": 3, "code": "signature_unsupported"} in first["notes"]
    refused = await post(
        client, workspace, form, first["id"], "/run", {"mapping": {**first["mapping"], "3": "q:sig"}, **RUN}
    )
    assert refused.status_code == 422 and refused.json()["code"] == "target_not_importable"
    done = await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    assert done.status_code == 202
    await run_job(first["id"])
    stored = (await stored_answers(workspace, form))[0]
    assert "sig" not in stored.answers


# ------------------------------------------------------------- the file's hour


async def _dies_after(monkeypatch, rows):
    repo = container.form_response_repo()
    real = repo.save_form_response
    calls = {"n": 0}

    async def dies(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == rows + 1:
            raise asyncio.CancelledError()
        return await real(*args, **kwargs)

    monkeypatch.setattr(repo, "save_form_response", dies)
    return repo, real


async def test_a_busy_import_past_its_hour_is_failed_undone_and_loses_its_file(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    repo, real = await _dies_after(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        await run_job(first["id"])
    monkeypatch.setattr(repo, "save_form_response", real)
    assert await count(workspace, form) == 2
    imports = container.response_import_repo()
    row = await imports.get_by_id(first["id"])
    assert row.status == ImportStatus.RUNNING
    later = row.expires_at + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    # the worker is not even stale: the hour alone ends it
    assert (await service().redefer_pending())["failed"] == 1
    row = await imports.get_by_id(first["id"])
    assert (row.status, row.error_code) == (ImportStatus.FAILED, "expired")
    assert await count(workspace, form) == 0
    assert await imports.count_files(first["id"]) == 0


async def test_a_queued_import_past_its_hour_is_failed_and_loses_its_file(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    imports = container.response_import_repo()
    later = (await imports.get_by_id(first["id"])).expires_at + dt.timedelta(seconds=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().redefer_pending())["failed"] == 1
    assert (await imports.get_by_id(first["id"])).error_code == "expired"
    assert await imports.count_files(first["id"]) == 0


async def test_a_running_job_stops_when_the_hour_ends_under_it(client: AsyncClient, workspace, monkeypatch):
    monkeypatch.setattr(limits, "BATCH_SIZE", 1)
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    imports = container.response_import_repo()
    expires = (await imports.get_by_id(first["id"])).expires_at
    repo = container.form_response_repo()
    real = repo.save_form_response
    calls = {"n": 0}

    async def slow(*args, **kwargs):
        calls["n"] += 1
        saved = await real(*args, **kwargs)
        if calls["n"] == 1:
            # the hour ends while the job is storing
            monkeypatch.setattr(service(), "_clock", lambda: expires + dt.timedelta(seconds=1))
        return saved

    monkeypatch.setattr(repo, "save_form_response", slow)
    assert await run_job(first["id"]) == "failed"
    row = await imports.get_by_id(first["id"])
    assert row.error_code == "expired"
    assert await count(workspace, form) == 0
    assert await imports.count_files(first["id"]) == 0


# ----------------------------------------------------------------- who confirmed


async def test_the_job_runs_as_the_one_who_confirmed_not_the_uploader(client: AsyncClient, workspace):
    fields = SIMPLE + [{"id": "note", "type": "short_text", "title": "Staff note", "internal": True}]
    form = await publish_form(workspace, fields, title="Who")
    admin = await member(workspace, WorkspaceRoles.ADMIN)
    header = HEADER + ["Internal: Staff note"]
    first = (await upload(client, workspace, form, csv_bytes([header, ["Ada", "36", "Red", "call back"]]))).json()
    queued = await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN}, user=admin)
    assert queued.status_code == 202
    assert await run_job(first["id"]) == "completed"
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.actor_id == str(testUser.id) and row.confirmed_by == str(admin.id)
    stored = (await stored_answers(workspace, form))[0]
    assert stored.internal_answers_meta["note"].updated_by == str(admin.id)
    shown = (await get(client, workspace, form, first["id"])).json()
    assert "confirmedBy" not in shown or shown["confirmedBy"] in (None, str(admin.id))


async def test_a_runner_demoted_before_the_job_gets_it_cancelled_whoever_uploaded(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    admin = await member(workspace, WorkspaceRoles.ADMIN)
    # the owner uploads (and could run it), the admin confirms
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN}, user=admin)
    link = await container.workspace_user_repo().find_workspace_user(workspace.id, admin.id)
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save_document(link)
    assert await run_job(first["id"]) == "cancelled"
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.error_code == "permission_removed"
    assert await count(workspace, form) == 0
    assert await container.response_import_repo().count_files(first["id"]) == 0


async def test_an_account_deleted_loses_its_name_as_the_confirmer_too(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    admin = await member(workspace, WorkspaceRoles.ADMIN)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN}, user=admin)
    await run_job(first["id"])
    await container.response_export_service().forget_actor(str(admin.id))
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.confirmed_by == "deleted-user" and row.actor_id == str(testUser.id)
