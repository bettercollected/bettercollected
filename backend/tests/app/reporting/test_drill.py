"""Drill-down: the responses behind one group of one card. The same filters and
conditions as the report, the group a card's count was made of, a page at a time
from a cursor, the scan stopped at a budget and said so, and nothing but ids and
plaintext columns in what comes back."""

import datetime as dt

import pytest

from backend.app.container import container
from backend.app.services.reporting import drill as drill_module
from backend.app.services.reporting import limits
from backend.app.services.reporting.policy import ReportFieldPolicy
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import add_member, cookies
from tests.app.reporting.helpers import (
    UTC,
    add_response,
    answer_choice,
    answer_choices,
    answer_number,
    answer_text,
    card,
    definition,
    groups_of,
    make_form,
    query,
    report_url,
    survey_fields,
)

pytestmark = pytest.mark.asyncio

KEYS = {"id", "submittedAt", "formVersion", "respondent"}


async def seeded(workspace):
    """Nine responses in time order; ids in the order they were stored."""
    form = await make_form(workspace, survey_fields())
    plan = [
        ("care", ["mail"], 5, False),
        ("it", ["chat"], 3, True),
        ("care", ["mail", "chat"], 4, False),
        ("hr", [], 2, False),
        ("care", ["wiki"], 5, True),
        ("it", ["mail"], 1, False),
        ("care", ["chat"], 2, False),
        ("it", [], 4, False),
        (None, ["mail"], None, False),
    ]
    ids = []
    for number, (dept, tools, score, known) in enumerate(plan):
        answers = {}
        if dept:
            answers["dept"] = answer_choice(dept)
        if tools:
            answers["tools"] = answer_choices(*tools)
        if score:
            answers["score"] = answer_number(score)
        answers["why"] = answer_text(f"private reason {number}")
        stored = await add_response(
            workspace, form, answers, identified=known, at=dt.datetime(2026, 3, 1 + number, 12, tzinfo=UTC), document=True
        )
        # what a response's page is opened by
        ids.append(stored.response_id)
    return form, ids


def drill_body(cards, card_id, group, filters=None, **extra):
    body = {"definition": definition(*cards, **({"filters": filters} if filters else {})), "card": card_id, "group": group}
    body.update(extra)
    return body


async def page(client, workspace, form, body, user=testUser):
    return await client.post(report_url(workspace, form, "responses"), json=body, cookies=cookies(user))


async def everything(client, workspace, form, body, size=2):
    """All pages of a drill-down, with the number of requests it took."""
    rows, requests, cursor = [], 0, None
    while True:
        extra = {"size": size, **({"cursor": cursor} if cursor else {})}
        response = await page(client, workspace, form, {**body, **extra})
        assert response.status_code == 200, response.text
        requests += 1
        data = response.json()
        rows.extend(data["responses"])
        cursor = data["cursor"]
        if data["exhausted"]:
            assert cursor is None
            return rows, requests
        assert cursor is not None and requests < 50


async def test_a_group_lists_the_responses_it_counted_oldest_first(client, workspace, reporting_on):
    form, ids = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept")]
    rows, _ = await everything(client, workspace, form, drill_body(cards, "dept", "care"), size=100)
    assert [r["id"] for r in rows] == [ids[0], ids[2], ids[4], ids[6]]
    # the report counts the same four
    counted = (await query(client, workspace, form, definition(*cards))).json()
    assert groups_of(counted, "dept")["care"]["n"] == len(rows)
    for row in rows:
        assert set(row) == KEYS and row["formVersion"] == 1


async def test_a_multiple_choice_group_holds_each_response_that_chose_it(client, workspace, reporting_on):
    form, ids = await seeded(workspace)
    cards = [card("tools", "bar", dimension="q:tools")]
    rows, _ = await everything(client, workspace, form, drill_body(cards, "tools", "mail"))
    assert [r["id"] for r in rows] == [ids[0], ids[2], ids[5], ids[8]]


async def test_pages_follow_one_another_with_nothing_twice_and_nothing_missed(client, workspace, reporting_on):
    form, ids = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept")]
    body = drill_body(cards, "dept", "care")
    first = (await page(client, workspace, form, {**body, "size": 3})).json()
    assert [r["id"] for r in first["responses"]] == [ids[0], ids[2], ids[4]]
    assert first["exhausted"] is False and first["cursor"]
    second = (await page(client, workspace, form, {**body, "size": 3, "cursor": first["cursor"]})).json()
    assert [r["id"] for r in second["responses"]] == [ids[6]]
    assert second["exhausted"] is True and second["cursor"] is None
    for size in (1, 2, 4, 100):
        rows, _ = await everything(client, workspace, form, body, size=size)
        assert [r["id"] for r in rows] == [ids[0], ids[2], ids[4], ids[6]], size


async def test_the_conditions_on_answers_narrow_the_group(client, workspace, reporting_on):
    form, ids = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept")]
    filters = {"where": [{"field": "q:score", "op": ">=", "value": 4}]}
    rows, _ = await everything(client, workspace, form, drill_body(cards, "dept", "care", filters))
    assert [r["id"] for r in rows] == [ids[0], ids[2], ids[4]]
    counted = (await query(client, workspace, form, definition(*cards, filters=filters))).json()
    assert groups_of(counted, "dept")["care"]["n"] == 3


async def test_a_group_of_a_plaintext_dimension(client, workspace, reporting_on):
    form, ids = await seeded(workspace)
    who = [card("who", "donut", dimension="respondent")]
    known, _ = await everything(client, workspace, form, drill_body(who, "who", "known"))
    assert [r["id"] for r in known] == [ids[1], ids[4]]
    assert {r["respondent"] for r in known} == {"known"}
    days = [card("day", "line", dimension={"field": "submitted_at", "bucket": "day"})]
    one, _ = await everything(client, workspace, form, drill_body(days, "day", "2026-03-04"))
    assert [r["id"] for r in one] == [ids[3]]
    versions = [card("v", "bar", dimension="form_version")]
    every, _ = await everything(client, workspace, form, drill_body(versions, "v", "1"))
    assert len(every) == 9


async def test_a_group_nobody_is_in_is_an_empty_end_of_the_set(client, workspace, reporting_on):
    form, _ = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept")]
    data = (await page(client, workspace, form, drill_body(cards, "dept", "no-such-group"))).json()
    assert data["responses"] == [] and data["exhausted"] is True and data["cursor"] is None and data["scanned"] == 9


async def test_the_scan_budget_ends_a_page_short_and_says_the_set_has_not_ended(client, workspace, reporting_on, monkeypatch):
    form, ids = await seeded(workspace)
    monkeypatch.setattr(limits, "BATCH_SIZE", 2)
    monkeypatch.setattr(limits, "DRILL_SCAN_MAX", 4)
    cards = [card("dept", "bar", dimension="q:dept")]
    body = {**drill_body(cards, "dept", "hr"), "size": 5}
    first = (await page(client, workspace, form, body)).json()
    # four read, none of them an "hr": a short, empty page that is not the end
    assert [r["id"] for r in first["responses"]] in ([ids[3]], [])
    assert first["exhausted"] is False and first["cursor"] and first["scanned"] >= 4
    # asking again from the cursor goes on, and reaches the end with the same single response
    found, cursor, rounds = list(first["responses"]), first["cursor"], 1
    while cursor:
        data = (await page(client, workspace, form, {**body, "cursor": cursor})).json()
        found += data["responses"]
        cursor, rounds = data["cursor"], rounds + 1
        assert rounds < 10
    assert [r["id"] for r in found] == [ids[3]]


async def test_what_comes_back_holds_no_answer_and_no_identity(client, workspace, reporting_on):
    form, ids = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept")]
    response = await page(client, workspace, form, drill_body(cards, "dept", "care"))
    text = response.text
    assert "private reason" not in text and "example.org" not in text and "person-" not in text
    assert response.headers["cache-control"] == "no-store"
    # only this form's responses
    other = await make_form(workspace, survey_fields(), title="Other")
    foreign = (await add_response(workspace, other, {"dept": answer_choice("care")}, document=True)).response_id
    rows, _ = await everything(client, workspace, form, drill_body(cards, "dept", "care"))
    assert foreign not in {r["id"] for r in rows}


# ----------------------------------------------------------------- refusals


@pytest.mark.parametrize(
    "mutate,status,code",
    [
        (lambda b: {**b, "card": "nope"}, 422, "invalid_definition"),
        (lambda b: {**b, "card": "total"}, 422, "op_not_allowed"),
        (lambda b: {**b, "card": "state"}, 422, "op_not_allowed"),
        (lambda b: {**b, "size": 0}, 422, "invalid_definition"),
        (lambda b: {**b, "size": limits.DRILL_PAGE_MAX + 1}, 422, "invalid_definition"),
        (lambda b: {**b, "group": ""}, 422, "invalid_definition"),
        (lambda b: {**b, "cursor": "not-a-cursor"}, 422, "invalid_definition"),
        (lambda b: {**b, "cursor": drill_module.encode_cursor.__module__}, 422, "invalid_definition"),
        (lambda b: {**b, "extra": 1}, 422, "invalid_definition"),
        (lambda b: {k: v for k, v in b.items() if k != "definition"}, 422, "invalid_definition"),
        (lambda b: {**b, "definition": definition(card("dept", "bar", dimension="q:nope"))}, 422, "unknown_field"),
        (lambda b: {**b, "definition": definition(card("dept", "bar", dimension="q:why"))}, 422, "field_not_reportable"),
        (lambda b: {**b, "definition": definition(card("dept", "bar", dimension="q:dept"), filters={"where": [{"field": "q:why", "op": "is_empty"}]})}, 422, "field_not_reportable"),
    ],
)
async def test_a_bad_request_is_refused_before_anything_is_read(client, workspace, reporting_on, mutate, status, code):
    form, _ = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept"), card("total", "tile"), card("state", "bar", dimension="status")]
    body = mutate(drill_body(cards, "dept", "care"))
    refused = await page(client, workspace, form, body)
    assert refused.status_code == status and refused.json()["code"] == code, refused.text


async def test_a_cursor_made_up_by_hand_cannot_leave_the_form(client, workspace, reporting_on):
    from backend.app.repositories.postgres.report_queries import Cursor

    form, ids = await seeded(workspace)
    other = await make_form(workspace, survey_fields(), title="Other")
    await add_response(workspace, other, {"dept": answer_choice("care")})
    cards = [card("dept", "bar", dimension="q:dept")]
    start = drill_module.encode_cursor(Cursor(0, dt.datetime(2000, 1, 1, tzinfo=UTC), "0" * 24))
    rows, _ = await everything(client, workspace, form, {**drill_body(cards, "dept", "care"), "cursor": start})
    assert len(rows) == 4


class HidingScore(ReportFieldPolicy):
    async def visible_fields(self, user, workspace_id, form_id, question_keys):
        return frozenset(question_keys) - {"q:score"}


async def test_a_question_the_caller_may_not_use_is_refused_as_one_that_does_not_exist(client, workspace, reporting_on, monkeypatch):
    form, _ = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept")]
    allowed = {"where": [{"field": "q:score", "op": ">=", "value": 3}]}
    ghost = await page(client, workspace, form, drill_body(cards, "dept", "care", {"where": [{"field": "q:nope", "op": ">=", "value": 3}]}))
    assert (await page(client, workspace, form, drill_body(cards, "dept", "care", allowed))).status_code == 200
    monkeypatch.setattr(container.report_service(), "_policy", HidingScore())
    container.report_service()._catalogues.clear()
    for body in (
        drill_body(cards, "dept", "care", allowed),
        drill_body([card("score", "bar", dimension="q:score")], "score", "5"),
    ):
        refused = await page(client, workspace, form, body)
        assert refused.status_code == 422 and refused.json()["code"] == "unknown_field"
    assert ghost.json()["code"] == "unknown_field"


# -------------------------------------------------------------- permissions


@pytest.mark.parametrize("role,allowed", [("OWNER", True), ("VIEWER", True), ("REVIEWER", True), ("PRIVACY_OFFICER", False)])
async def test_the_role_decides_as_for_a_query(client, workspace, reporting_on, role, allowed):
    form, _ = await seeded(workspace)
    member = await add_member(workspace, role)
    cards = [card("dept", "bar", dimension="q:dept")]
    response = await page(client, workspace, form, drill_body(cards, "dept", "care"), user=member)
    assert response.status_code == (200 if allowed else 403), response.text


async def test_a_privacy_officer_is_refused_before_an_answer_is_decrypted(client, workspace, reporting_on, monkeypatch):
    from backend.app.services.reporting import engine

    form, _ = await seeded(workspace)
    officer = await add_member(workspace, "PRIVACY_OFFICER")

    def forbidden(*args, **kwargs):
        raise AssertionError("an answer was decrypted")

    monkeypatch.setattr(engine, "stored_answers", forbidden)
    cards = [card("dept", "bar", dimension="q:dept")]
    assert (await page(client, workspace, form, drill_body(cards, "dept", "care"), user=officer)).status_code == 403


async def test_a_busy_server_answers_429_and_a_slow_pass_503(client, workspace, reporting_on, monkeypatch):
    import asyncio

    form, _ = await seeded(workspace)
    cards = [card("dept", "bar", dimension="q:dept")]
    service = container.report_service()
    monkeypatch.setattr(limits, "PASS_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(service, "_passes", asyncio.Semaphore(0))
    busy = await page(client, workspace, form, drill_body(cards, "dept", "care"))
    assert busy.status_code == 429 and busy.json()["code"] == "report_busy"
    monkeypatch.setattr(service, "_passes", asyncio.Semaphore(limits.PASSES_AT_ONCE))
    monkeypatch.setattr(limits, "PASS_SECONDS", 0.05)

    async def stuck(*args, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(service._engine, "drill", stuck)
    slow = await page(client, workspace, form, drill_body(cards, "dept", "care"))
    assert slow.status_code == 503 and slow.json()["code"] == "report_timeout"
    assert service._passes._value == limits.PASSES_AT_ONCE
