"""The CSV of one card of a report (``POST .../report/export``): who may download,
what the file holds, that it is audited before it is handed out (ids and counts
only), that nothing is stored, and the places the pass takes (a workspace's share
of the replicas'). Everything here is synthetic."""

import asyncio
import json

import pytest

from backend.app.container import container
from backend.app.schemas.form_access_grant import ROLE_REVIEWER, ROLE_VIEWER
from backend.app.schemas.workspace_audit_event import REPORT_EXPORTED, RESPONSE_EXPORT
from backend.app.services.reporting import limits
from backend.app.services.reporting import service as service_module
from tests.app.form_access.helpers import add_member, audit_events, fail_audit, grant, restrict
from tests.app.reporting.helpers import (
    add_response,
    answer_choice,
    answer_number,
    card,
    choice_question,
    definition,
    make_form,
    report_url,
    survey_fields,
)
from tests.app.form_access.helpers import cookies
from tests.app.controllers.data import testUser

pytestmark = pytest.mark.asyncio

BY_DEPT = card("c1", "bar", dimension="q:dept", measures=[{"agg": "count"}, {"agg": "avg", "field": "q:score"}])


async def seeded(workspace):
    form = await make_form(workspace, survey_fields(), title="Volunteers")
    await add_response(workspace, form, {"dept": answer_choice("care"), "score": answer_number(4)})
    await add_response(workspace, form, {"dept": answer_choice("care"), "score": answer_number(2)})
    await add_response(workspace, form, {"dept": answer_choice("it"), "score": answer_number(5)})
    await add_response(workspace, form, {"score": answer_number(1)})
    return form


async def download(client, workspace, form, body=None, user=testUser, **extra):
    payload = body if body is not None else {"definition": definition(BY_DEPT), "card": "c1", "format": "csv"}
    return await client.post(
        report_url(workspace, form, "export"), json=payload, cookies=cookies(user), **extra
    )


def lines_of(response):
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return text[1:].split("\r\n")


async def test_the_csv_holds_the_cards_table_and_says_what_it_is(client, workspace, reporting_on):
    form = await seeded(workspace)
    response = await download(client, workspace, form)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith("attachment;")
    lines = lines_of(response)
    assert lines[0] == "Report,Volunteers"
    assert "Responses in the card,4" in lines
    assert any(line.startswith("Time zone,UTC") for line in lines)
    assert any(line.startswith('"Generated at (UTC, ISO 8601)",') for line in lines)
    assert "Filters,None" in lines
    at = lines.index("Group,Responses,Share of answered (%),Average of Score")
    table = [line for line in lines[at + 1 :] if line]
    assert "Care,2,66.7,3" in table
    assert "IT,1,33.3,5" in table
    # the same figures the screen gets
    screen = await client.post(report_url(workspace, form), json=definition(BY_DEPT), cookies=cookies(testUser))
    groups = {g["label"]: g["n"] for g in screen.json()["cards"][0]["groups"]}
    assert groups["Care"] == 2 and groups["IT"] == 1


async def test_a_card_with_no_dimension_is_one_row_and_the_filters_are_in_words(client, workspace, reporting_on):
    form = await seeded(workspace)
    body = definition(
        card("t", "tile"),
        filters={"formVersion": [1], "respondent": "anonymous", "where": [{"field": "q:dept", "op": "is", "value": "care"}]},
        tz="Europe/Amsterdam",
    )
    response = await download(client, workspace, form, {"definition": body, "card": "t", "format": "csv"})
    assert response.status_code == 200, response.text
    lines = lines_of(response)
    filters = next(line for line in lines if line.startswith("Filters,"))
    assert "Form versions 1" in filters and "Respondents: anonymous" in filters and "Conditions on answers: 1" in filters
    # the condition is counted, not stated: a value asked about is an answer
    assert "care" not in filters.lower()
    assert any(line.startswith("Time zone,Europe/Amsterdam") for line in lines)
    assert "All responses,2," in lines


async def test_only_the_asked_card_is_computed(client, workspace, reporting_on, monkeypatch):
    form = await seeded(workspace)
    seen = []
    original = container.report_service()._engine.scan

    async def spy(scope, workspace_id, form_id, plan, catalogue):
        seen.append([c.id for c in plan.cards])
        return await original(scope, workspace_id, form_id, plan, catalogue)

    monkeypatch.setattr(container.report_service()._engine, "scan", spy)
    body = definition(BY_DEPT, card("c2", "bar", dimension="q:remote"), card("c3", "tile"))
    response = await download(client, workspace, form, {"definition": body, "card": "c2", "format": "csv"})
    assert response.status_code == 200
    assert seen == [["c2"]]


async def test_text_that_a_spreadsheet_would_run_is_neutralised(client, workspace, reporting_on):
    fields = [choice_question("dept", {"a": "=HYPERLINK(\"x\")", "b": "+31 6 1234", "c": "Fine, with comma"}, "Department")]
    form = await make_form(workspace, fields, title="=cmd|' /C calc'!A0")
    for option in ("a", "b", "c"):
        await add_response(workspace, form, {"dept": answer_choice(option)})
    body = {"definition": definition(card("c1", "bar", dimension="q:dept")), "card": "c1", "format": "csv"}
    response = await download(client, workspace, form, body)
    assert response.status_code == 200, response.text
    lines = lines_of(response)
    assert lines[0].startswith("Report,'=cmd")
    table = "\n".join(lines)
    assert "'=HYPERLINK" in table and "'+31 6 1234" in table
    assert '"Fine, with comma"' in table
    assert not any(line.startswith(("=", "+", "-", "@")) for line in lines)


async def test_the_file_is_audited_with_ids_and_counts_only(client, workspace, reporting_on):
    form = await seeded(workspace)
    assert await audit_events(workspace, REPORT_EXPORTED) == []
    assert (await download(client, workspace, form)).status_code == 200
    (row,) = await audit_events(workspace, REPORT_EXPORTED)
    assert row.user_id == testUser.id and row.form_id == form.form_id
    assert row.export_format == "csv" and row.export_channel == "report"
    # groups written: Care, IT, and the others' row is not there (no more groups)
    assert row.count == len([g for g in (await groups_of_screen(client, workspace, form))])
    dumped = json.dumps(row.model_dump(mode="json"))
    for secret in ("Care", "Department", "dept", "Volunteers", "score", "c1"):
        assert secret not in dumped
    # the row exports of the responses are counted apart
    assert await audit_events(workspace, RESPONSE_EXPORT) == []


async def groups_of_screen(client, workspace, form):
    screen = await client.post(report_url(workspace, form), json=definition(BY_DEPT), cookies=cookies(testUser))
    return screen.json()["cards"][0]["groups"]


async def test_no_audit_row_means_no_file_and_nothing_is_stored(client, workspace, reporting_on, monkeypatch):
    form = await seeded(workspace)
    fail_audit(monkeypatch)
    response = await download(client, workspace, form)
    assert response.status_code == 503 and response.json()["code"] == "audit_unavailable"
    assert b"Volunteers" not in response.content and b"Care" not in response.content
    assert await audit_events(workspace, REPORT_EXPORTED) == []


async def test_a_download_refused_before_the_file_writes_no_entry_and_gives_the_download_back(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "REPORT_MAX_ROWS", 2)
    form = await seeded(workspace)
    refused = await download(client, workspace, form)
    assert refused.status_code == 413 and refused.json()["code"] == "too_many_rows"
    assert await audit_events(workspace, REPORT_EXPORTED) == []
    verdict = await container.rate_limiter().hit(
        f"report-export:{workspace.id}:{form.form_id}", str(testUser.id),
        limits.EXPORTS_PER_WINDOW, limits.EXPORT_WINDOW_SECONDS, amount=0,
    )
    assert verdict.count == 0


@pytest.mark.parametrize(
    "role,allowed",
    [
        ("OWNER", True),
        ("ADMIN", True),
        ("EDITOR", True),
        # read the report, but the file is what leaves the screen
        ("REVIEWER", False),
        ("VIEWER", False),
        ("PRIVACY_OFFICER", False),
    ],
)
async def test_the_role_decides(client, workspace, reporting_on, role, allowed):
    form = await seeded(workspace)
    member = await add_member(workspace, role)
    response = await download(client, workspace, form, user=member)
    assert response.status_code == (200 if allowed else 403), response.text
    rows = await audit_events(workspace, REPORT_EXPORTED)
    assert len(rows) == (1 if allowed else 0)


async def test_an_export_grant_lets_a_viewer_download(client, workspace, reporting_on, form_access_on):
    form = await seeded(workspace)
    viewer = await add_member(workspace, "VIEWER")
    reviewer = await add_member(workspace, "REVIEWER")
    await restrict(workspace, form.form_id)
    await grant(workspace, form.form_id, viewer.id, ROLE_VIEWER, export=True)
    await grant(workspace, form.form_id, reviewer.id, ROLE_REVIEWER, export=False)
    assert (await download(client, workspace, form, user=viewer)).status_code == 200
    assert (await download(client, workspace, form, user=reviewer)).status_code == 403
    stranger = await add_member(workspace, "EDITOR")
    assert (await download(client, workspace, form, user=stranger)).status_code == 404


async def test_a_privacy_officer_is_refused_before_anything_is_read(client, workspace, reporting_on, monkeypatch):
    from backend.app.services.reporting import engine

    form = await seeded(workspace)
    officer = await add_member(workspace, "PRIVACY_OFFICER")

    def forbidden(*args, **kwargs):
        raise AssertionError("an answer was decrypted")

    monkeypatch.setattr(engine, "stored_answers", forbidden)
    assert (await download(client, workspace, form, user=officer)).status_code == 403


async def test_a_stranger_and_a_signed_out_caller_are_refused(client, workspace, workspace_1, reporting_on):
    from tests.app.controllers.data import testUser1

    form = await seeded(workspace)
    assert (await download(client, workspace, form, user=testUser1)).status_code in (403, 404)
    anonymous = await client.post(
        report_url(workspace, form, "export"),
        json={"definition": definition(BY_DEPT), "card": "c1", "format": "csv"},
    )
    assert anonymous.status_code in (401, 403)


@pytest.mark.parametrize(
    "body",
    [
        {"definition": definition(BY_DEPT), "card": "nope", "format": "csv"},
        {"definition": definition(BY_DEPT), "card": "c1", "format": "xlsx"},
        {"definition": definition(BY_DEPT), "card": "c1", "format": "csv", "extra": 1},
        {"definition": {"v": 2}, "card": "c1", "format": "csv"},
        {"definition": definition(card("c1", "bar", dimension="q:ghost")), "card": "c1", "format": "csv"},
    ],
)
async def test_an_invalid_request_is_422_and_writes_nothing(client, workspace, reporting_on, body):
    form = await seeded(workspace)
    response = await download(client, workspace, form, body)
    assert response.status_code == 422, response.text
    assert await audit_events(workspace, REPORT_EXPORTED) == []


async def test_a_downloads_per_hour_limit_is_its_own(client, workspace, reporting_on, monkeypatch):
    monkeypatch.setattr(limits, "EXPORTS_PER_WINDOW", 2)
    form = await seeded(workspace)
    for _ in range(2):
        assert (await download(client, workspace, form)).status_code == 200
    third = await download(client, workspace, form)
    assert third.status_code == 429 and third.json()["code"] == "rate_limited"
    assert int(third.headers["retry-after"]) >= 1
    # a query is not counted against it
    assert (await client.post(report_url(workspace, form), json=definition(BY_DEPT), cookies=cookies(testUser))).status_code == 200


async def test_a_card_counted_in_sql_needs_no_pass(client, workspace, reporting_on, monkeypatch):
    form = await seeded(workspace)
    monkeypatch.setattr(container.report_service(), "_passes", asyncio.Semaphore(0))
    monkeypatch.setattr(limits, "PASS_WAIT_SECONDS", 0.05)
    body = {"definition": definition(card("v", "bar", dimension="form_version")), "card": "v", "format": "csv"}
    assert (await download(client, workspace, form, body)).status_code == 200
    busy = await download(client, workspace, form)
    assert busy.status_code == 429 and busy.json()["code"] == "report_busy"


# ----------------------------------------- a workspace's share of the replicas' places


async def places(client_name: str) -> int:
    verdict = await container.rate_limiter().hit(
        service_module.SLOT_SCOPE, client_name,
        limits.PASSES_ACROSS_REPLICAS, limits.PASS_SLOTS_WINDOW_SECONDS, amount=0,
    )
    return verdict.count


async def test_one_workspace_cannot_take_more_than_its_share(client, workspace, reporting_on):
    form = await seeded(workspace)
    limiter = container.rate_limiter()
    mine = f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}"
    assert limits.PASSES_PER_WORKSPACE < limits.PASSES_ACROSS_REPLICAS
    # as many passes in flight for this workspace as it may hold
    for _ in range(limits.PASSES_PER_WORKSPACE):
        assert (await limiter.admit(
            service_module.SLOT_SCOPE, mine, limits.PASSES_PER_WORKSPACE, limits.PASS_SLOTS_WINDOW_SECONDS
        )).allowed
    busy = await client.post(report_url(workspace, form), json=definition(BY_DEPT), cookies=cookies(testUser))
    assert busy.status_code == 429 and busy.json()["code"] == "report_busy"
    # the refused pass took no place of the replicas' and a count in SQL needs none
    assert await places(service_module.SLOT_CLIENT) == 0
    ok = await client.post(report_url(workspace, form), json=definition(card(dimension="form_version")), cookies=cookies(testUser))
    assert ok.status_code == 200
    # the share given back lets the next one in, and a finished pass leaves nothing held
    await limiter.release(service_module.SLOT_SCOPE, mine, limits.PASS_SLOTS_WINDOW_SECONDS)
    assert (await client.post(report_url(workspace, form), json=definition(BY_DEPT), cookies=cookies(testUser))).status_code == 200
    assert await places(mine) == limits.PASSES_PER_WORKSPACE - 1
    assert await places(service_module.SLOT_CLIENT) == 0


async def test_another_workspace_still_has_places_when_one_holds_its_share(
    client, workspace, workspace_1, reporting_on
):
    from tests.app.controllers.data import testUser1

    form = await seeded(workspace)
    other = await make_form(workspace_1, survey_fields(), user=testUser1)
    await add_response(workspace_1, other, {"dept": answer_choice("care"), "score": answer_number(3)})
    limiter = container.rate_limiter()
    for _ in range(limits.PASSES_PER_WORKSPACE):
        await limiter.admit(
            service_module.SLOT_SCOPE, f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}",
            limits.PASSES_PER_WORKSPACE, limits.PASS_SLOTS_WINDOW_SECONDS,
        )
    assert (await client.post(report_url(workspace, form), json=definition(BY_DEPT), cookies=cookies(testUser))).status_code == 429
    fine = await client.post(
        report_url(workspace_1, other), json=definition(BY_DEPT), cookies=cookies(testUser1)
    )
    assert fine.status_code == 200, fine.text


async def test_a_pass_refused_by_the_replicas_gives_its_workspace_share_back(client, workspace, reporting_on):
    form = await seeded(workspace)
    limiter = container.rate_limiter()
    for _ in range(limits.PASSES_ACROSS_REPLICAS):
        await limiter.admit(
            service_module.SLOT_SCOPE, service_module.SLOT_CLIENT,
            limits.PASSES_ACROSS_REPLICAS, limits.PASS_SLOTS_WINDOW_SECONDS,
        )
    busy = await client.post(report_url(workspace, form), json=definition(BY_DEPT), cookies=cookies(testUser))
    assert busy.status_code == 429 and busy.json()["code"] == "report_busy"
    assert await places(f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}") == 0
    assert container.report_service()._passes._value == limits.PASSES_AT_ONCE


async def test_the_drill_down_takes_the_same_places(client, workspace, reporting_on, monkeypatch):
    form = await seeded(workspace)
    service = container.report_service()
    held = []
    original = service._engine.drill

    async def spy(*args, **kwargs):
        held.append(
            (await places(f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}"), await places(service_module.SLOT_CLIENT))
        )
        return await original(*args, **kwargs)

    monkeypatch.setattr(service._engine, "drill", spy)
    body = {"definition": definition(BY_DEPT), "card": "c1", "group": "care"}
    response = await client.post(report_url(workspace, form, "responses"), json=body, cookies=cookies(testUser))
    assert response.status_code == 200, response.text
    assert held == [(1, 1)]
    assert await places(f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}") == 0
    assert await places(service_module.SLOT_CLIENT) == 0
    # a workspace at its share is refused a drill-down too
    limiter = container.rate_limiter()
    for _ in range(limits.PASSES_PER_WORKSPACE):
        await limiter.admit(
            service_module.SLOT_SCOPE, f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}",
            limits.PASSES_PER_WORKSPACE, limits.PASS_SLOTS_WINDOW_SECONDS,
        )
    busy = await client.post(report_url(workspace, form, "responses"), json=body, cookies=cookies(testUser))
    assert busy.status_code == 429 and busy.json()["code"] == "report_busy"


async def test_a_request_cancelled_while_it_gives_its_places_back_still_frees_the_process_slot(
    client, workspace, reporting_on, monkeypatch
):
    service = container.report_service()

    async def cancelled(client_name):
        raise asyncio.CancelledError()

    monkeypatch.setattr(service, "_give_back", cancelled)
    with pytest.raises(asyncio.CancelledError):
        async with service._place(workspace.id):
            pass
    # the semaphore does not wait on the shared places: two such disconnects must not leave the replica busy
    assert service._passes._value == limits.PASSES_AT_ONCE


async def test_a_request_cancelled_inside_the_pass_gives_every_place_back(client, workspace, reporting_on):
    service = container.report_service()
    inside = asyncio.Event()

    async def held():
        async with service._place(workspace.id):
            inside.set()
            await asyncio.sleep(30)

    task = asyncio.ensure_future(held())
    await inside.wait()
    assert await places(f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}") == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert service._passes._value == limits.PASSES_AT_ONCE
    assert await places(f"{service_module.SLOT_WORKSPACE_PREFIX}{workspace.id}") == 0
    assert await places(service_module.SLOT_CLIENT) == 0
