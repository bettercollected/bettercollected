"""Taking the audit log out as a file (``AUDIT_LOG_UI_ENABLED``): CSV and JSON of
the filtered view, the same permission and filters as the list, a Privacy
officer's file as bare as their screen, the export recorded before it starts,
the cap and the budget. Everything here is synthetic."""

import csv
import datetime as dt
import io
import json
from unittest.mock import AsyncMock, patch

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.audit_log_dto import AuditEntryDto
from backend.app.schemas import workspace_audit_event as E
from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
from backend.app.services.audit_log import export as X
from backend.app.services.audit_log import catalog
from backend.app.services.audit_log.mode import OFF_CODE
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    fail_audit,
    restrict,
)

pytestmark = pytest.mark.asyncio

BASE = dt.datetime(2026, 10, 1, 8, 0, tzinfo=dt.timezone.utc)
SESSION = "sid-secret-0001"
NAME = "Name"


@pytest.fixture(autouse=True)
def switched_on(monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", True)


@pytest.fixture(autouse=True)
def auth_service():
    """Every id is answered with a display name and an address (the address must
    never reach a file)."""

    async def get(url, **kwargs):
        ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {
            "users_info": [
                {
                    "_id": i,
                    "first_name": NAME,
                    "last_name": i[-6:],
                    "email": f"{i}@mail.voorbeeld.example",
                }
                for i in ids
            ]
        }

    with patch("common.services.http_client.HttpClient.get", AsyncMock(side_effect=get)) as m:
        yield m


async def seed(workspace, event, minutes=0, user_id=None, **fields):
    document = WorkspaceAuditEventDocument(
        id=RecordId(),
        workspace_id=workspace.id,
        user_id=user_id if user_id is not None else testUser.id,
        session_id=fields.pop("session_id", SESSION),
        event=event,
        created_at=BASE + dt.timedelta(minutes=minutes),
        **fields,
    )
    await container.workspace_audit_repo().record(document)
    return document


def url(workspace, form=None, tail="/export") -> str:
    return api(workspace) + (f"/forms/{form}/audit-log{tail}" if form else f"/audit-log{tail}")


async def get(client, workspace, user=testUser, form=None, **params):
    return await client.get(url(workspace, form), cookies=cookies(user), params=params)


def table(response) -> list:
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.DictReader(io.StringIO(text[1:])))


# -- the switch and who may ----------------------------------------------------------------
async def test_both_routes_answer_422_and_read_nothing_while_the_switch_is_off(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", False)
    await seed(workspace, E.ACCESS_MODE_CHANGED, form_id=workspace_form.form_id)
    for who in (testUser, testUser1):
        for form in (None, workspace_form.form_id):
            response = await get(client, workspace, who, form=form)
            assert response.status_code == 422, response.text
            assert response.json()["code"] == OFF_CODE
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []


@pytest.mark.parametrize(
    "roles,status",
    [
        (["ADMIN"], 200),
        (["OWNER"], 200),
        (["PRIVACY_OFFICER"], 200),
        (["COLLABORATOR"], 403),
        (["EDITOR"], 403),
        (["REVIEWER"], 403),
        (["VIEWER"], 403),
        ([], 403),
    ],
)
async def test_only_audit_read_opens_either_export(
    client: AsyncClient, workspace, workspace_form, roles, status
):
    member = await add_member(workspace, *roles)
    await seed(workspace, E.ACCESS_MODE_CHANGED, form_id=workspace_form.form_id)
    for form in (None, workspace_form.form_id):
        response = await get(client, workspace, member, form=form)
        assert response.status_code == status, (form, response.text)
        if status == 403:
            assert E.ACCESS_MODE_CHANGED not in response.text
    # a refused export is not recorded
    rows = await audit_events(workspace, E.AUDIT_LOG_EXPORTED)
    assert len(rows) == (2 if status == 200 else 0)


async def test_strangers_and_the_signed_out_are_refused(
    client: AsyncClient, workspace, workspace_form
):
    for form in (None, workspace_form.form_id):
        assert (await get(client, workspace, testUser1, form=form)).status_code == 403
        assert (await client.get(url(workspace, form))).status_code == 401
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []


async def test_a_form_of_another_workspace_is_not_found(
    client: AsyncClient, workspace, workspace_1, workspace_form
):
    response = await client.get(
        url(workspace_1, workspace_form.form_id), cookies=cookies(testUser)
    )
    assert response.status_code in (403, 404), response.text
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []


# -- the files --------------------------------------------------------------------------------
async def test_csv_is_one_row_per_entry_newest_first_with_names_beside_the_ids(
    client: AsyncClient, workspace, workspace_form
):
    form = workspace_form.form_id
    admin = await add_member(workspace, "ADMIN")
    older = await seed(workspace, E.ACCESS_MODE_CHANGED, 1, form_id=form, access_mode="restricted")
    newer = await seed(
        workspace, E.MEMBER_ROLE_CHANGED, 2, target_user_id=admin.id, role="ADMIN", previous_role="VIEWER"
    )
    response = await get(client, workspace)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].count("audit-log-") >= 1
    rows = table(response)
    assert [r["id"] for r in rows] == [str(newer.id), str(older.id)]
    assert list(rows[0]) == X.CSV_COLUMNS
    first, second = rows
    assert first["at"] == "2026-10-01T08:02:00Z" and first["area"] == "members"
    assert first["actor_id"] == testUser.id and first["actor_name"] == f"{NAME} {testUser.id[-6:]}"
    assert first["target_name"] == f"{NAME} {admin.id[-6:]}"
    assert (first["role"], first["previous_role"]) == ("ADMIN", "VIEWER")
    assert second["form_id"] == form and second["form_title"]
    assert second["access_mode"] == "restricted" and second["target_user_id"] == ""
    # the address the auth service knows is never in a file
    assert "mail.voorbeeld.example" not in response.text


async def test_json_has_the_same_entries_in_camel_case(client: AsyncClient, workspace):
    seeded = await seed(workspace, E.RESPONSES_DELETED, 1, count=12)
    response = await get(client, workspace, format="json")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = json.loads(response.content)
    assert body["exportedAt"].endswith("Z")
    (entry,) = body["entries"]
    assert entry["id"] == str(seeded.id) and entry["event"] == E.RESPONSES_DELETED
    assert entry["count"] == 12 and entry["actorId"] == testUser.id
    assert set(entry) == {X.JSON_KEYS[c] for c in X.CSV_COLUMNS}
    assert response.headers["content-disposition"].count(".json") >= 1


async def test_an_empty_result_is_a_valid_file(client: AsyncClient, workspace):
    csv_reply = await get(client, workspace, area="forms")
    assert csv_reply.status_code == 200 and table(csv_reply) == []
    json_reply = await get(client, workspace, format="json", area="forms")
    assert json.loads(json_reply.content)["entries"] == []


async def test_the_format_must_be_csv_or_json(client: AsyncClient, workspace):
    for bad in ("xml", "CSV", "", "csv;rm"):
        response = await get(client, workspace, format=bad)
        assert response.status_code == 422, bad
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []


async def test_a_file_holds_no_field_the_list_does_not_return(
    client: AsyncClient, workspace, workspace_form
):
    """Rows come from the list's own DTO: what is stored but never shown (an
    invitation, an export's id, another workspace's ids) is in no file."""
    other_workspace = str(RecordId())
    await seed(
        workspace,
        E.FORM_PROMOTED,
        1,
        form_id=workspace_form.form_id,
        source_workspace_id=other_workspace,
        source_form_id="src-form-1",
        invitation_id="inv-secret-1",
        export_id="exp-secret-1",
        connection_id="conn-secret-1",
    )
    for fmt in ("csv", "json"):
        response = await get(client, workspace, format=fmt)
        assert response.status_code == 200, response.text
        for hidden in (other_workspace, "src-form-1", "inv-secret-1", "exp-secret-1", "conn-secret-1"):
            assert hidden not in response.text, (fmt, hidden)
    assert set(X.CSV_COLUMNS) == set(AuditEntryDto.model_fields) | {c[0] for c in X.NAME_COLUMNS}


async def test_csv_cells_that_would_be_formulas_are_neutralised(
    client: AsyncClient, workspace, workspace_form
):
    async def get_http(url_, **kwargs):
        ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {"users_info": [{"_id": i, "first_name": "=HYPERLINK(\"x\")", "last_name": "+1"} for i in ids]}

    await seed(workspace, E.ACCESS_MODE_CHANGED, 1, form_id=workspace_form.form_id)
    with patch("common.services.http_client.HttpClient.get", AsyncMock(side_effect=get_http)):
        response = await get(client, workspace)
    (row,) = table(response)
    assert row["actor_name"].startswith("'=")
    assert not any(v.lstrip().startswith(("=", "+", "@")) for v in row.values() if v)


# -- the same filters as the list ----------------------------------------------------------------
async def test_the_export_holds_exactly_what_the_list_shows_for_each_filter(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    monkeypatch.setattr(X, "EXPORTS_PER_WINDOW", 1000)
    form = workspace_form.form_id
    other = await add_member(workspace, "ADMIN")
    for i in range(6):
        await seed(workspace, E.ACCESS_MODE_CHANGED, i, form_id=form, access_mode="restricted")
    await seed(workspace, E.MEMBER_ROLE_CHANGED, 7, user_id=other.id, target_user_id=testUser.id, role="ADMIN")
    await seed(workspace, E.RESPONSES_DELETED, 8, count=3)
    await seed(workspace, E.SSO_BREAK_GLASS_REQUEST, 9, method="GET", path="/x")
    await seed(workspace, E.TOTP_ENROLLED, 10)  # account-level: never in any feed

    filters = [
        {},
        {"area": "access"},
        {"area": ["access", "members"]},
        {"event": E.RESPONSES_DELETED},
        {"actor": other.id},
        {"target": testUser.id},
        {"involving": other.id},
        {"form_id": form},
        {"from": "2026-10-01T08:03:00Z", "to": "2026-10-01T08:07:00Z"},
        {"area": "security"},
    ]
    async def listed_ids(**params):
        reply = await client.get(
            api(workspace) + "/audit-log",
            cookies=cookies(testUser),
            params={**params, "limit": 100},
        )
        assert reply.status_code == 200, params
        return [e["id"] for e in reply.json()["entries"]]

    for params in filters:
        # an export records itself, so each file is compared with the list read
        # just before it (the file holds what existed when it was asked for)
        before = await listed_ids(**params)
        exported = await get(client, workspace, **params)
        assert exported.status_code == 200, params
        assert before == [r["id"] for r in table(exported)], params
        before = await listed_ids(**params)
        as_json = await get(client, workspace, format="json", **params)
        assert before == [e["id"] for e in json.loads(as_json.content)["entries"]], params
    # the form's own export is the form's own list
    form_list = await client.get(
        url(workspace, form, ""), cookies=cookies(testUser), params={"limit": 100}
    )
    exported = await get(client, workspace, form=form)
    assert [e["id"] for e in form_list.json()["entries"]] == [r["id"] for r in table(exported)]
    assert len(table(exported)) >= 6


async def test_a_filter_that_is_not_valid_is_refused_like_the_list(
    client: AsyncClient, workspace
):
    for params in (
        {"area": "nonsense"},
        {"event": "nonsense"},
        {"from": "2026-10-02T00:00:00Z", "to": "2026-10-01T00:00:00Z"},
        {"actor": "bad id!"},
    ):
        listed = await client.get(
            api(workspace) + "/audit-log", cookies=cookies(testUser), params=params
        )
        exported = await get(client, workspace, **params)
        assert exported.status_code == listed.status_code == 422, params
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []


async def test_the_export_takes_every_filter_of_the_list(client: AsyncClient):
    app = client._transport.app
    schema = app.openapi()["paths"]
    prefix = next(p for p in schema if p.endswith("/workspaces/{workspace_id}/audit-log")).rsplit(
        "/audit-log", 1
    )[0]

    def names(path):
        return {p["name"] for p in schema[prefix + path]["get"]["parameters"]} - {"workspace_id", "form_id"}

    assert names("/audit-log") - {"cursor", "limit"} == names("/audit-log/export") - {"format"}
    assert names("/forms/{form_id}/audit-log") - {"cursor", "limit"} == names(
        "/forms/{form_id}/audit-log/export"
    ) - {"format"}


# -- a Privacy officer's file is as bare as their screen ------------------------------------------
async def test_a_privacy_officer_gets_no_response_id_and_no_session_id_in_either_file(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    form = workspace_form.form_id
    await restrict(workspace, form)
    officer = await add_member(workspace, "PRIVACY_OFFICER")
    admin = await add_member(workspace, "ADMIN")
    response_id = str(RecordId())
    await seed(
        workspace, E.RESPONSE_REVISION_READ, 2, user_id=admin.id, form_id=form,
        response_id=response_id, revision=3,
    )
    for who, link, session in ((testUser, True, True), (admin, True, True), (officer, False, False)):
        for form_feed in (None, form):
            for fmt in ("csv", "json"):
                response = await get(client, workspace, who, form=form_feed, format=fmt)
                assert response.status_code == 200, (who.id, response.text)
                assert (response_id in response.text) is link, (who.id, fmt)
                assert (SESSION in response.text) is session, (who.id, fmt)
                # who did what to which form is there for everyone
                assert admin.id in response.text and form in response.text
                assert "mail.voorbeeld.example" not in response.text


# -- the entry ---------------------------------------------------------------------------------------
async def test_an_export_is_recorded_before_it_starts_with_names_of_filters_never_values(
    client: AsyncClient, workspace, workspace_form
):
    form = workspace_form.form_id
    await seed(workspace, E.ACCESS_MODE_CHANGED, 1, form_id=form)
    await seed(workspace, E.ACCESS_MODE_CHANGED, 2, form_id=form)
    seen = {}
    repo = container.workspace_audit_repo()
    original = X.AuditLogExport._bytes

    async def wrapped(text, workspace_id):
        # the body has not started: the entry is already stored
        seen["before_body"] = len(await audit_events(workspace, E.AUDIT_LOG_EXPORTED))
        async for part in original(text, workspace_id):
            yield part

    with patch.object(X.AuditLogExport, "_bytes", staticmethod(wrapped)):
        response = await get(
            client, workspace, format="json", area="access", actor=testUser.id, form_id=form,
            **{"from": "2026-09-01T00:00:00Z"},
        )
    assert response.status_code == 200, response.text
    assert seen["before_body"] == 1
    (row,) = await audit_events(workspace, E.AUDIT_LOG_EXPORTED)
    assert row.user_id == testUser.id and row.export_format == "json" and row.count == 2
    assert row.export_filters == ["area", "actor", "form", "from"]
    # a form filter of the workspace export is a filter name, not the entry's form
    assert row.form_id is None
    # no value of a filter, no name, no row content in the entry
    present = {k: v for k, v in row.model_dump().items() if v is not None}
    # nothing but the format, the count and the filters' names is stored (a form's own export adds its id)
    assert set(present) - {"id", "workspace_id", "user_id", "session_id", "event", "created_at", "updated_at"} == {
        "count", "export_format", "export_filters",
    }
    assert not {"actor", "area", "from"} & {str(v) for v in present.values() if isinstance(v, str)}
    assert "2026-09-01" not in row.model_dump_json()
    assert (await audit_events(workspace, E.AUDIT_LOG_EXPORTED)) == [row]
    assert repo is container.workspace_audit_repo()


async def test_the_entry_of_a_form_export_names_the_form_and_the_entry_shows_in_the_log(
    client: AsyncClient, workspace, workspace_form
):
    form = workspace_form.form_id
    assert (await get(client, workspace, form=form)).status_code == 200
    (row,) = await audit_events(workspace, E.AUDIT_LOG_EXPORTED)
    assert row.form_id == form and row.export_format == "csv" and row.count == 0
    page = await client.get(
        api(workspace) + "/audit-log",
        cookies=cookies(testUser),
        params={"event": E.AUDIT_LOG_EXPORTED},
    )
    (entry,) = page.json()["entries"]
    assert entry["event"] == E.AUDIT_LOG_EXPORTED and entry["area"] == "security"
    assert entry["exportFormat"] == "csv" and entry["count"] == 0
    assert catalog.area_of(E.AUDIT_LOG_EXPORTED) == catalog.AREA_SECURITY


async def test_an_export_that_cannot_be_recorded_is_not_made(
    client: AsyncClient, workspace, monkeypatch
):
    await seed(workspace, E.ACCESS_MODE_CHANGED, 1)
    fail_audit(monkeypatch)
    for fmt in ("csv", "json"):
        response = await get(client, workspace, format=fmt)
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "audit_unavailable"
        assert E.ACCESS_MODE_CHANGED not in response.text


async def test_reading_the_list_is_not_recorded(client: AsyncClient, workspace):
    await seed(workspace, E.ACCESS_MODE_CHANGED, 1)
    page = await client.get(api(workspace) + "/audit-log", cookies=cookies(testUser))
    assert page.status_code == 200
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []


# -- the cap and the budget --------------------------------------------------------------------------
async def test_more_than_the_cap_is_refused_before_anything_is_recorded_or_sent(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(X, "MAX_ROWS", 3)
    for i in range(4):
        await seed(workspace, E.ACCESS_MODE_CHANGED, i)
    response = await get(client, workspace)
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "too_many_rows"
    assert E.ACCESS_MODE_CHANGED not in response.text
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []
    # narrowing the filters brings it under the cap
    ok = await get(client, workspace, **{"from": (BASE + dt.timedelta(minutes=1)).isoformat()})
    assert ok.status_code == 200 and len(table(ok)) == 3


async def test_exactly_the_cap_is_allowed(client: AsyncClient, workspace, monkeypatch):
    monkeypatch.setattr(X, "MAX_ROWS", 3)
    for i in range(3):
        await seed(workspace, E.ACCESS_MODE_CHANGED, i)
    response = await get(client, workspace)
    assert response.status_code == 200 and len(table(response)) == 3


async def test_a_file_is_walked_in_batches_and_is_complete(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(X, "BATCH", 4)
    seeded = [await seed(workspace, E.ACCESS_MODE_CHANGED, i // 3) for i in range(11)]
    expected = [
        str(d.id) for d in sorted(seeded, key=lambda d: (d.created_at, str(d.id)), reverse=True)
    ]
    only = {"event": E.ACCESS_MODE_CHANGED}
    assert [r["id"] for r in table(await get(client, workspace, **only))] == expected
    body = json.loads((await get(client, workspace, format="json", **only)).content)
    assert [e["id"] for e in body["entries"]] == expected


async def test_the_walk_never_sends_more_than_the_cap_whatever_arrived_since_the_count(
    monkeypatch,
):
    monkeypatch.setattr(X, "MAX_ROWS", 5)

    async def batches():
        for _ in range(4):
            yield [object(), object()], None

    got = [len(entries) async for entries, _ in X.AuditLogExport._limited(batches(), 5)]
    assert got == [2, 2, 1]


async def test_a_person_has_a_budget_of_exports_and_a_request_refused_after_the_scan_has_used_it(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(X, "EXPORTS_PER_WINDOW", 2)
    monkeypatch.setattr(X, "MAX_ROWS", 1)
    await seed(workspace, E.ACCESS_MODE_CHANGED, 1)
    await seed(workspace, E.ACCESS_MODE_CHANGED, 2)
    # over the cap: refused, and each refusal used a slot (it scanned), so
    # repeating it cannot scan for free
    assert (await get(client, workspace)).status_code == 413
    assert (await get(client, workspace)).status_code == 413
    third = await get(client, workspace)
    assert third.status_code == 429, third.text
    assert third.json()["code"] == "rate_limited" and int(third.headers["retry-after"]) >= 1
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []
    # another person has their own budget
    narrow = {"from": (BASE + dt.timedelta(minutes=2)).isoformat(), "event": E.ACCESS_MODE_CHANGED}
    admin = await add_member(workspace, "ADMIN")
    assert (await get(client, workspace, admin, **narrow)).status_code == 200
    assert (await get(client, workspace, admin, **narrow)).status_code == 200
    again = await get(client, workspace, admin, **narrow)
    assert again.status_code == 429
    assert len(await audit_events(workspace, E.AUDIT_LOG_EXPORTED)) == 2


async def test_a_failed_scan_gives_the_slot_back_and_a_refusal_before_it_never_took_one(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(X, "EXPORTS_PER_WINDOW", 1)
    reader = container.audit_log_reader()
    real = reader.count_up_to

    async def broken(scope, cap):
        raise RuntimeError("store down")

    monkeypatch.setattr(reader, "count_up_to", broken)
    for _ in range(3):
        assert (await get(client, workspace)).status_code == 500
    monkeypatch.setattr(reader, "count_up_to", real)
    # the slot came back each time: the one export of the window is still there
    assert (await get(client, workspace)).status_code == 200
    # refusals made before the scan (an invalid filter, no permission) took none
    other = await add_member(workspace, "ADMIN")
    assert (await get(client, workspace, other, area="nonsense")).status_code == 422
    assert (await get(client, workspace, testUser1)).status_code == 403
    assert (await get(client, workspace, other)).status_code == 200


# -- a link on another site cannot start one ---------------------------------------------------------
@pytest.mark.parametrize("mode", ["navigate", "no-cors", "same-origin", "websocket", "NAVIGATE"])
async def test_a_browser_navigation_or_subresource_cannot_start_an_export(
    client: AsyncClient, workspace, workspace_form, mode
):
    """The cookie is SameSite=Lax: a followed link (``Sec-Fetch-Mode: navigate``)
    carries it, so such a request is refused, before anything is read, recorded
    or counted against the budget."""
    for form in (None, workspace_form.form_id):
        response = await client.get(
            url(workspace, form),
            cookies=cookies(testUser),
            headers={"Sec-Fetch-Mode": mode, "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Dest": "document"},
        )
        assert response.status_code == 403, (mode, response.text)
        assert response.json()["code"] == "export_needs_fetch"
    assert await audit_events(workspace, E.AUDIT_LOG_EXPORTED) == []


async def test_the_dashboards_fetch_and_clients_that_send_no_fetch_metadata_still_export(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(X, "EXPORTS_PER_WINDOW", 3)
    # the dashboard asks with fetch (cors), from its own site or a custom domain
    for site in ("same-origin", "same-site", "cross-site"):
        response = await client.get(
            url(workspace),
            cookies=cookies(testUser),
            headers={"Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": site, "Sec-Fetch-Dest": "empty"},
        )
        assert response.status_code == 200, (site, response.text)
    # a script or curl sends none of these headers
    monkeypatch.setattr(X, "EXPORTS_PER_WINDOW", 10)
    assert (await get(client, workspace)).status_code == 200
    # and the refused navigations above spent no budget: the count is the four exports
    assert len(await audit_events(workspace, E.AUDIT_LOG_EXPORTED)) == 4
