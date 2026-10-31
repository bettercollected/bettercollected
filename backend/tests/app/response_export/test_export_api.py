"""Streaming a small export: the CSV, its columns and filters, the guard against
formulas, the roles, the rate limit and the audit entry."""

import datetime as dt
import json

import pytest
from common.models.user import User
from common.records import RecordId
from httpx import AsyncClient
from sqlalchemy import text as sql

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.filter_queries.response_export import ResponseExportFilters
from backend.app.schemas.response_export import ExportKind, ExportStatus
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.response_export import limits
from tests.app.controllers.data import invited_user, testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
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


async def audit_of(workspace, form):
    return await container.response_export_repo().list_for_form(workspace.id, form.form_id)


async def test_a_small_export_streams_the_csv(client: AsyncClient, workspace):
    form = await publish(workspace, hidden=["utm_source"])
    await submit(workspace, form, answers("Ada"), hidden={"utm_source": "mail"})
    await submit(workspace, form, answers("=SUM(1)", phone="-12.5"))
    response = await start(client, workspace, form)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert 'filename="Export test.csv"' in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")
    table = rows(response)
    assert table[0] == [
        "Responder ID", "Full name", "Phone", "Age", "Colours",
        "Response ID", "Submitted at (UTC, ISO 8601)", "Hidden: utm_source",
    ]
    by_name = {r[1]: r for r in table[1:]}
    ada = by_name["Ada"]
    assert ada[0] == testUser.sub
    assert ada[2:5] == ["'+31 6 1234", "30", "Red; Blue"]
    assert ada[5] and ada[6].endswith("Z") and ada[7] == "mail"
    # respondent text never becomes a formula; a plain negative number stays one
    assert by_name["'=SUM(1)"][2] == "-12.5"


async def test_the_file_name_survives_a_hostile_form_title(client: AsyncClient, workspace):
    form = await publish(workspace, title='Étude "2026"; a/b\r\nX-Evil: 1')
    await submit(workspace, form)
    response = await start(client, workspace, form)
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert disposition.startswith("attachment; filename=")
    assert "filename*=UTF-8''%C3%89tude" in disposition
    assert "x-evil" not in response.headers


async def test_the_audit_entry_records_who_what_and_how_many_but_no_answers(
    client: AsyncClient, workspace
):
    form = await publish(workspace)
    await submit_many(workspace, form, 3, prefix="Secretname")
    response = await start(
        client,
        workspace,
        form,
        {"columns": ["q:name", "response_id"], "search": "someone@example.org", "respondent": "known"},
    )
    assert response.status_code == 200
    (entry,) = await audit_of(workspace, form)
    assert entry.actor_id == testUser.id and str(entry.workspace_id) == str(workspace.id)
    assert entry.kind == ExportKind.STREAM and entry.status == ExportStatus.COMPLETED
    assert entry.row_count == 0 and entry.expected_rows == 0
    assert entry.columns == ["q:name", "response_id"]
    assert entry.filters == {"respondent": "known", "search": True}
    assert entry.finished_at and entry.created_at
    stored = json.dumps(entry.model_dump(mode="json"))
    assert "someone@example.org" not in stored and "Secretname" not in stored
    # no answer content in the database row either
    assert "Secretname" not in json.dumps(
        [e.model_dump(mode="json") for e in await container.response_export_repo().many()]
    )


async def test_an_export_that_holds_rows_counts_them(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    assert (await start(client, workspace, form)).status_code == 200
    (entry,) = await audit_of(workspace, form)
    assert entry.row_count == entry.expected_rows == 3
    assert entry.columns[0] == "responder" and entry.filters == {}


async def test_an_interrupted_stream_is_recorded_as_such(workspace, monkeypatch):
    form = await publish(workspace)
    await submit_many(workspace, form, 2)
    service = container.response_export_service()
    started = await service.request(
        workspace.id, form.form_id, testUser, None, ResponseExportFilters()
    )
    body = started.body
    first = await body.__anext__()
    assert first
    await body.aclose()
    (entry,) = await audit_of(workspace, form)
    assert entry.status == ExportStatus.CANCELLED and entry.error_code == "interrupted"


# ------------------------------------------------------------------- filters


async def test_the_list_filters_narrow_an_export(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    repo = container.form_response_repo()
    stored = sorted(await repo.many(), key=lambda r: str(r.id))
    stored[0].dataOwnerIdentifier = "known@example.org"
    stored[0].form_version = 2
    stored[1].dataOwnerIdentifier = None
    stored[2].dataOwnerIdentifier = ""
    for response in stored:
        await repo.upsert(response)
    # the stored time is the row's own column
    async with container.pg_engine().begin() as conn:
        await conn.execute(
            sql("UPDATE app.form_responses SET created_at = :at WHERE id = :id"),
            {"at": dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc), "id": str(stored[1].id)},
        )

    async def ask(**body):
        response = await start(client, workspace, form, body)
        assert response.status_code == 200, response.text
        return rows(response)[1:]

    assert len(await ask()) == 3
    assert [r[0] for r in await ask(respondent="known")] == ["known@example.org"]
    assert len(await ask(respondent="anonymous")) == 2
    assert [r[0] for r in await ask(search="KNOWN@")] == ["known@example.org"]
    assert len(await ask(formVersion=[2])) == 1
    assert len(await ask(submittedTo="2021-01-01T00:00:00Z")) == 1
    assert len(await ask(submittedFrom="2021-01-01T00:00:00Z")) == 2
    assert len(await ask(submittedFrom="2021-01-01T00:00:00Z", respondent="known")) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"submittedFrom": "2026-01-01T00:00:00"},
        {"submittedFrom": "2026-02-01T00:00:00Z", "submittedTo": "2026-01-01T00:00:00Z"},
        {"respondent": "robots"},
        {"formVersion": [-1]},
        {"search": "x" * 400},
        {"surprise": True},
    ],
)
async def test_an_invalid_filter_is_refused(client: AsyncClient, workspace, body):
    form = await publish(workspace)
    response = await start(client, workspace, form, body)
    assert response.status_code == 422
    assert await audit_of(workspace, form) == []


async def test_chosen_columns_and_unknown_ones(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit(workspace, form)
    chosen = await start(client, workspace, form, {"columns": ["submitted_at", "q:phone"]})
    assert rows(chosen)[0] == ["Phone", "Submitted at (UTC, ISO 8601)"]
    for body, code in (({"columns": ["q:nope"]}, "unknown_column"), ({"columns": []}, "no_columns")):
        refused = await start(client, workspace, form, body)
        assert refused.status_code == 422 and refused.json()["code"] == code
    listed = await client.get(url(workspace, form, "/columns"), cookies=_cookies(testUser))
    assert [c["key"] for c in listed.json()][:2] == ["responder", "q:name"]


async def test_a_group_exported_as_rows_comes_as_a_zip(client: AsyncClient, workspace):
    form = await publish(workspace, fields=GROUP_FIELDS)
    given = answers("Ada")
    given["jobs"] = {
        "type": "group",
        "items": [
            {"employer": {"type": "text", "text": "Acme"}},
            {"employer": {"type": "text", "text": "=cmd"}},
        ],
    }
    await submit(workspace, form, given)
    response = await start(client, workspace, form)
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"].count(".zip") >= 1
    files = zip_rows(response.content)
    assert list(files) == ["Export test.csv", "Export test - Jobs.csv"]
    main, jobs = files["Export test.csv"], files["Export test - Jobs.csv"]
    assert "Jobs (Job count)" in main[0]
    assert main[1][main[0].index("Jobs (Job count)")] == "2"
    assert jobs[0] == ["Response ID", "Job", "Employer"]
    assert [r[1:] for r in jobs[1:]] == [["1", "Acme"], ["2", "'=cmd"]]
    assert jobs[1][0] == main[1][main[0].index("Response ID")]


async def test_a_response_without_answers_is_not_exported(client: AsyncClient, workspace):
    form = await publish(workspace)
    await submit(workspace, form)
    repo = container.form_response_repo()
    (stored,) = await repo.many()
    stub = stored.model_copy(deep=True)
    stub.id = RecordId()
    stub.response_id = "stub"
    stub.answers = None
    await repo.upsert(stub)
    response = await start(client, workspace, form)
    assert len(rows(response)) == 2


# --------------------------------------------------------------------- roles


async def member(workspace, user: User, role):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=[role])
    )


@pytest.mark.parametrize(
    "role,allowed",
    [
        (WorkspaceRoles.ADMIN, True),
        (WorkspaceRoles.COLLABORATOR, True),
        (WorkspaceRoles.REVIEWER, False),
        (WorkspaceRoles.VIEWER, False),
        (WorkspaceRoles.PRIVACY_OFFICER, False),
    ],
)
async def test_only_a_role_that_may_export_exports(client, workspace, role, allowed):
    other = User(id=str(RecordId()), sub="role@example.com")
    await member(workspace, other, role)
    form = await publish(workspace)
    await submit(workspace, form)
    before = len(await audit_of(workspace, form))
    paths = [
        ("post", url(workspace, form)),
        ("get", url(workspace, form)),
        ("get", url(workspace, form, "/columns")),
        ("get", url(workspace, form, "/someid")),
    ]
    for method, path in paths:
        response = await getattr(client, method)(path, cookies=_cookies(other))
        if allowed:
            assert response.status_code in (200, 404), (method, path, response.text)
        else:
            assert response.status_code == 403, (method, path, response.text)
            # nothing of the answers in a refusal
            assert "Ada" not in response.text
    if not allowed:
        assert len(await audit_of(workspace, form)) == before


async def test_a_stranger_and_the_signed_out_get_nothing(client, workspace):
    form = await publish(workspace)
    await submit(workspace, form)
    refused = await client.post(url(workspace, form), json={}, cookies=_cookies(testUser1))
    assert refused.status_code == 403
    assert (await client.post(url(workspace, form), json={})).status_code == 401
    # another workspace's form is not found, not exportable by naming it
    other = await publish(workspace)
    other_path = f"/api/v1/workspaces/{RecordId()}/forms/{other.form_id}/exports"
    assert (await client.post(other_path, json={}, cookies=_cookies(testUser))).status_code in (403, 404)


async def test_an_unknown_form_is_not_found(client, workspace):
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/nope/exports", json={}, cookies=_cookies(testUser)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------- rate limit


async def test_exports_are_rate_limited_per_user_and_form(client, workspace, monkeypatch):
    monkeypatch.setattr(limits, "REQUESTS_PER_WINDOW", 2)
    form = await publish(workspace)
    second_form = await publish(workspace)
    await submit(workspace, form)
    for _ in range(2):
        assert (await start(client, workspace, form)).status_code == 200
    refused = await start(client, workspace, form)
    assert refused.status_code == 429
    assert refused.json()["code"] == "rate_limited"
    assert int(refused.headers["retry-after"]) >= 1
    # not for the other form, nor for another user
    assert (await start(client, workspace, second_form)).status_code == 200
    assert (await start(client, workspace, form, user=invited_user)).status_code == 200
    # a refused request is not an export
    assert len(await audit_of(workspace, form)) == 3


async def test_the_limit_ends_with_its_window(client, workspace, monkeypatch, rate_limit_clock):
    monkeypatch.setattr(limits, "REQUESTS_PER_WINDOW", 1)
    form = await publish(workspace)
    assert (await start(client, workspace, form)).status_code == 200
    assert (await start(client, workspace, form)).status_code == 429
    rate_limit_clock["now"] += limits.WINDOW_SECONDS + 1
    assert (await start(client, workspace, form)).status_code == 200


async def test_too_big_an_export_asks_to_narrow_the_filters(client, workspace, monkeypatch):
    monkeypatch.setattr(limits, "MAX_ROWS", 2)
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    response = await start(client, workspace, form)
    assert response.status_code == 413 and response.json()["code"] == "too_many_rows"
    assert await audit_of(workspace, form) == []
