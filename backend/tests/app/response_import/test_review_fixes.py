"""The review's findings, one test each: the form alias across workspaces, the
takeover path, a failed undo, the file's hour, content types, option sources,
the problem cap, headings never in clear, the switch for queued jobs, the
check/run limit."""

import asyncio
import datetime as dt
import json

import pytest
from common.clock import utcnow
from common.records import RecordId
from httpx import AsyncClient
from sqlalchemy import text as sql

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.response_import import ImportStatus
from backend.app.services.response_import import limits
from backend.app.services.response_import.service import _Problems
from backend.app.services.response_import.targets import STATUS_UNSUPPORTED, build_targets
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.response_import.helpers import (
    csv_bytes,
    get,
    post,
    publish_form,
    run_job,
    service,
    stored_answers,
    upload,
    url,
)
from tests.app.response_import.test_flow import HEADER, SIMPLE, count, member, simple_form

pytestmark = pytest.mark.asyncio

ROWS = [HEADER, ["Ada", "36", "Red"], ["Bob", "40", "Blue"], ["Cy", "50", "Red"]]
RUN = {"confirmedLawfulBasis": True}


# ------------------------------------------------------------------------- B1


async def test_a_custom_url_equal_to_another_workspaces_form_id_reaches_nothing(
    client: AsyncClient, workspace, workspace_1
):
    mine = await simple_form(workspace)
    foreign = await publish_form(workspace_1, SIMPLE, user=testUser1, title="Theirs")
    # the alias: my form's custom URL is the other form's id
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(workspace_id=workspace.id, query=str(mine.form_id))
    link.settings.custom_url = str(foreign.form_id)
    await repo.save_document(link)
    assert (
        await repo.get_workspace_form_in_workspace(workspace_id=workspace.id, query=str(foreign.form_id))
    ) is not None  # the lookup by id or custom URL does find it: the import must not use it

    mapping = {"mapping": {"0": "q:name"}}
    first = (await upload(client, workspace, mine, csv_bytes(ROWS))).json()
    ghost = type("F", (), {"form_id": foreign.form_id})()
    calls = [
        ("post", url(workspace, ghost), {"content": csv_bytes(ROWS), "headers": {"content-type": "text/csv"}}),
        ("get", url(workspace, ghost), {}),
        ("get", url(workspace, ghost, f"/{first['id']}"), {}),
        ("post", url(workspace, ghost, f"/{first['id']}/check"), {"json": mapping}),
        ("post", url(workspace, ghost, f"/{first['id']}/run"), {"json": {**mapping, **RUN}}),
        ("post", url(workspace, ghost, f"/{first['id']}/rollback"), {"json": {}}),
        ("delete", url(workspace, ghost, f"/{first['id']}"), {}),
    ]
    for method, path, kwargs in calls:
        response = await getattr(client, method)(path, cookies=_cookies(testUser), **kwargs)
        assert response.status_code == 404, (method, path, response.status_code, response.text)
        # nothing of the other form: no targets, no titles
        assert "targets" not in response.text and "Full name" not in response.text
    # no row anywhere under the other form, in my workspace or theirs
    assert await container.response_import_repo().list_for_form(workspace.id, str(foreign.form_id)) == []
    assert await count(workspace_1, foreign) == 0
    # and my own form still imports
    assert (await get(client, workspace, mine, first["id"])).status_code == 200


async def test_the_job_never_runs_on_a_form_reached_by_alias(client: AsyncClient, workspace, workspace_1):
    foreign = await publish_form(workspace_1, SIMPLE, user=testUser1, title="Theirs")
    mine = await simple_form(workspace)
    first = (await upload(client, workspace, mine, csv_bytes(ROWS))).json()
    await post(client, workspace, mine, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    # a row pointing at the other form's id (as the alias would have written it)
    def point(row):
        row.form_id = str(foreign.form_id)
        return row

    await container.response_import_repo().update_locked(first["id"], point)
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(workspace_id=workspace.id, query=str(mine.form_id))
    link.settings.custom_url = str(foreign.form_id)
    await repo.save_document(link)
    assert await run_job(first["id"]) == "cancelled"
    assert await count(workspace_1, foreign) == 0


# ------------------------------------------------------------------------- S1


async def test_a_retry_that_is_cancelled_still_clears_what_the_first_attempt_stored(
    client: AsyncClient, workspace, monkeypatch
):
    form = await simple_form(workspace)
    admin = await member(workspace, WorkspaceRoles.ADMIN)
    first = (await upload(client, workspace, form, csv_bytes(ROWS), user=admin)).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN}, user=admin)
    repo = container.form_response_repo()
    real = repo.save_form_response
    calls = {"n": 0}

    async def dies(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise asyncio.CancelledError()
        return await real(*args, **kwargs)

    monkeypatch.setattr(repo, "save_form_response", dies)
    with pytest.raises(asyncio.CancelledError):
        await run_job(first["id"])
    monkeypatch.setattr(repo, "save_form_response", real)
    assert await count(workspace, form) == 2
    # before the sweep takes the job up again the importer loses the role
    link = await container.workspace_user_repo().find_workspace_user(workspace.id, admin.id)
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save_document(link)
    later = utcnow() + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    assert (await service().redefer_pending())["queued"] == 1
    assert await run_job(first["id"]) == "cancelled"
    assert await count(workspace, form) == 0


async def test_a_retry_that_finds_its_file_gone_clears_what_the_first_attempt_stored(
    client: AsyncClient, workspace, monkeypatch
):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    repo = container.form_response_repo()
    real = repo.save_form_response
    calls = {"n": 0}

    async def dies(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise asyncio.CancelledError()
        return await real(*args, **kwargs)

    monkeypatch.setattr(repo, "save_form_response", dies)
    with pytest.raises(asyncio.CancelledError):
        await run_job(first["id"])
    monkeypatch.setattr(repo, "save_form_response", real)
    await container.response_import_repo().delete_file(first["id"])
    later = utcnow() + limits.STALE_RUNNING_AFTER + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: later)
    await service().redefer_pending()
    assert await run_job(first["id"]) == "failed"
    assert (await container.response_import_repo().get_by_id(first["id"])).error_code == "file_gone"
    assert await count(workspace, form) == 0


# ------------------------------------------------------------------------- S2


async def test_an_undo_that_fails_can_be_asked_again(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    await run_job(first["id"])
    repo = container.form_response_repo()
    real = repo.delete_imported

    async def broken(*args, **kwargs):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(repo, "delete_imported", broken)
    with pytest.raises(RuntimeError):
        await service().rollback(workspace.id, str(form.form_id), first["id"], testUser)
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.status == ImportStatus.COMPLETED and row.rolled_back_at is None
    assert await count(workspace, form) == 3
    monkeypatch.setattr(repo, "delete_imported", real)
    done = await client.post(url(workspace, form, f"/{first['id']}/rollback"), json={}, cookies=_cookies(testUser))
    assert done.status_code == 200 and done.json()["rolledBackCount"] == 3
    assert await count(workspace, form) == 0


async def test_an_account_deleted_loses_its_name_on_an_undo_it_did_for_a_colleague(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    await run_job(first["id"])
    admin = await member(workspace, WorkspaceRoles.ADMIN)
    assert (
        await client.post(url(workspace, form, f"/{first['id']}/rollback"), json={}, cookies=_cookies(admin))
    ).status_code == 200
    assert (await container.response_import_repo().get_by_id(first["id"])).rolled_back_by == str(admin.id)
    await container.response_export_service().forget_actor(str(admin.id))
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.rolled_back_by == "deleted-user" and row.actor_id == str(testUser.id)


# ------------------------------------------------------------------------- S3


async def test_a_check_late_in_the_hour_does_not_extend_the_files_expiry(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    repo = container.response_import_repo()
    expires = (await repo.get_by_id(first["id"])).expires_at
    assert expires is not None
    late = utcnow() + dt.timedelta(minutes=50)
    monkeypatch.setattr(service(), "_clock", lambda: late)
    assert (await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})).status_code == 202
    assert await run_job(first["id"]) == "checked"
    assert (await repo.get_by_id(first["id"])).expires_at == expires
    # past the hour the file is gone, whatever was done with it meanwhile
    after = expires + dt.timedelta(minutes=1)
    monkeypatch.setattr(service(), "_clock", lambda: after)
    assert (await service().purge_expired())["expired"] == 1
    assert await repo.count_files(first["id"]) == 0


# ------------------------------------------------------------------------- S4


async def test_the_upload_takes_text_csv_only(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    data = csv_bytes(ROWS)
    for kind in ("text/plain", "application/octet-stream", "application/x-www-form-urlencoded", "application/vnd.ms-excel"):
        response = await client.post(url(workspace, form), content=data, headers={"content-type": kind}, cookies=_cookies(testUser))
        assert response.status_code == 415, kind
    # no content type at all
    bare = await client.post(url(workspace, form), content=data, cookies=_cookies(testUser))
    assert bare.status_code == 415
    assert await container.response_import_repo().list_for_form(workspace.id, str(form.form_id)) == []
    assert (await upload(client, workspace, form, data)).status_code == 201
    assert (await upload(client, workspace, form, data, content_type="text/csv; charset=utf-8")).status_code == 201


async def test_check_run_and_undo_take_json_only(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    body = json.dumps({"mapping": first["mapping"], "confirmedLawfulBasis": True}).encode()
    for tail in ("/check", "/run", "/rollback"):
        for headers in ({"content-type": "text/plain"}, {"content-type": "application/x-www-form-urlencoded"}, {}):
            response = await client.post(
                url(workspace, form, f"/{first['id']}{tail}"), content=body, headers=headers, cookies=_cookies(testUser)
            )
            assert response.status_code == 415, (tail, headers)
            assert response.json()["code"] == "json_required"
    # nothing was queued by any of them
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.status == ImportStatus.UPLOADED


# ------------------------------------------------------------------------- S5


def test_a_question_with_an_option_source_cannot_be_imported():
    form = {
        "builder_version": "v2",
        "title": "F",
        "fields": [
            {
                "id": "s1",
                "type": "slide",
                "index": 0,
                "properties": {
                    "fields": [
                        {"id": "plain", "type": "dropdown", "title": "Plain", "properties": {"choices": [{"id": "a", "value": "A"}]}},
                        {
                            "id": "sourced",
                            "type": "dropdown",
                            "title": "Sourced",
                            "properties": {"option_source": {"type": "list", "list_id": "L"}},
                        },
                    ]
                },
            }
        ],
    }
    found = {t.key: t for t in build_targets(form)}
    assert found["q:plain"].status == "ok"
    assert (found["q:sourced"].status, found["q:sourced"].reason) == (STATUS_UNSUPPORTED, "option_source_unsupported")


# ------------------------------------------------------------------------- S6


def test_problems_are_counted_exactly_and_only_the_first_are_kept():
    log = _Problems()
    for row in range(100_000):
        log.add([{"row": row, "column": 0, "code": "required" if row % 2 else "format"}])
    assert len(log.listed) == limits.PROBLEMS_LISTED
    assert log.total == 100_000 and log.truncated
    assert log.counts == {"required": 50_000, "format": 50_000}
    assert log.listed[0]["row"] == 0


async def test_a_file_of_nothing_but_problems_lists_the_first_and_counts_all(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    rows = [HEADER] + [["", "x", "Nope"] for _ in range(300)]
    first = (await upload(client, workspace, form, csv_bytes(rows))).json()
    await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})
    await run_job(first["id"])
    body = (await get(client, workspace, form, first["id"])).json()
    assert len(body["problems"]) == limits.PROBLEMS_LISTED and body["problemsTruncated"] is True
    assert body["problemCounts"]["invalid_number"] == 300 and body["problemCounts"]["unknown_option"] == 300
    assert body["rowsInvalid"] == 300 and body["rowsValid"] == 0


# ------------------------------------------------------------------------ S10


async def test_headings_are_never_stored_in_clear(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    # a file without a heading row: the first "heading" is a person's data
    secret = "Zebediah.Quentin@example.org"
    data = csv_bytes([[secret, "36", "Red"], ["Bob", "40", "Blue"]])
    first = (await upload(client, workspace, form, data)).json()
    assert first["headers"] == [secret, "36", "Red"]
    engine = container.pg_engine()
    async with engine.connect() as conn:
        for table in ("response_imports", "response_import_files"):
            dump = (await conn.execute(sql(f"SELECT doc::text FROM app.{table}"))).scalars().all()
            assert dump and all("Zebediah" not in d and secret not in d for d in dump), table
    # the screens still get them while the file waits
    shown = (await get(client, workspace, form, first["id"])).json()
    assert shown["headers"] == [secret, "36", "Red"]
    # and none once it is gone
    await post(client, workspace, form, first["id"], "/run", {"mapping": {"0": "q:name"}, **RUN})
    await run_job(first["id"])
    assert (await get(client, workspace, form, first["id"])).json()["headers"] == []


# ------------------------------------------------------------------------- N3


async def test_a_queued_job_does_nothing_once_the_switch_is_off(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], **RUN})
    monkeypatch.setattr(settings, "CSV_IMPORT_ENABLED", False)
    assert await run_job(first["id"]) == "cancelled"
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.error_code == "switched_off"
    assert await count(workspace, form) == 0
    assert await container.response_import_repo().count_files(first["id"]) == 0


# ------------------------------------------------------------------------- N7


async def test_checks_and_runs_are_limited_per_person(client: AsyncClient, workspace, monkeypatch):
    monkeypatch.setattr(limits, "RUNS_PER_WINDOW", 1)
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS))).json()
    assert (await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})).status_code == 202
    await run_job(first["id"])
    limited = await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})
    assert limited.status_code == 429 and limited.json()["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) > 0
