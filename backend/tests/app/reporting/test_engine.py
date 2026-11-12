"""The engine's bounds and bookkeeping: the cap, deleted responses, the cache and
what invalidates it, the field-policy seam, the group limits, unreadable answers,
the deletion-request and feedback built-ins, and the limiter."""

import asyncio
import base64

import pytest
from sqlalchemy import update

from backend.app.container import container
from backend.app.services.reporting import engine as engine_module
from backend.app.services.reporting import limits
from backend.app.services.reporting.policy import ReportFieldPolicy
from backend.db.models import FormResponseRow
from common.models.standard_form import RespondentFeedback
from tests.app.controllers.data import testUser
from tests.app.reporting.helpers import (
    UTC,
    add_many,
    add_response,
    answer_bool,
    answer_choice,
    answer_currency,
    answer_number,
    card,
    card_of,
    definition,
    groups_of,
    make_form,
    query,
    survey_fields,
)

pytestmark = pytest.mark.asyncio


async def run(client, workspace, form, *cards, user=testUser, **changes):
    response = await query(client, workspace, form, definition(*cards, **changes), user=user)
    assert response.status_code == 200, response.text
    return response.json()


def dept(n, **extra):
    return {"answers": {"dept": answer_choice("care")}, **extra}


# ------------------------------------------------------------------ the cap


async def test_above_the_cap_the_query_is_refused_with_the_count_never_partial(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "REPORT_MAX_ROWS", 5)
    form = await make_form(workspace, survey_fields())
    await add_many(workspace, form, [dept(i) for i in range(6)])
    scanned = []
    real = engine_module.ReportEngine.scan

    async def spy(self, *args, **kwargs):
        scanned.append(1)
        return await real(self, *args, **kwargs)

    monkeypatch.setattr(engine_module.ReportEngine, "scan", spy)
    response = await query(client, workspace, form, definition(card(dimension="q:dept")))
    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "too_many_rows" and body["count"] == 6 and body["max"] == 5
    assert "cards" not in body
    # refused before a single answer was read
    assert scanned == []
    # at the cap exactly it is fine
    narrowed = await run(
        client, workspace, form, card(dimension="q:dept"), filters={"respondent": "known"}
    )
    assert narrowed["n"] == 0
    await container.form_response_repo().delete_by_form_id(form.form_id)
    await add_many(workspace, form, [dept(i) for i in range(5)])
    assert (await run(client, workspace, form, card(dimension="q:dept")))["n"] == 5


async def test_the_cap_covers_only_cards_that_read_answers(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "REPORT_MAX_ROWS", 3)
    form = await make_form(workspace, survey_fields())
    await add_many(workspace, form, [dept(i) for i in range(5)])
    result = await run(client, workspace, form, card("t", "tile"), card("v", "bar", dimension="form_version"))
    assert result["n"] == 5 and result["scanned"] == 0
    assert groups_of(result, "v")["1"]["n"] == 5
    mixed = await query(
        client, workspace, form, definition(card("t", "tile"), card("d", "bar", dimension="q:dept"))
    )
    assert mixed.status_code == 413 and mixed.json()["count"] == 5


async def test_responses_that_arrive_during_the_pass_refuse_it_rather_than_cut_it(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "REPORT_MAX_ROWS", 4)
    monkeypatch.setattr(limits, "BATCH_SIZE", 2)
    form = await make_form(workspace, survey_fields())
    await add_many(workspace, form, [dept(i) for i in range(6)])
    repo = container.report_repo()

    async def stale_token(scope, filters):
        return 3, 0  # the count the pass started from

    monkeypatch.setattr(repo, "token", stale_token)
    response = await query(client, workspace, form, definition(card(dimension="q:dept")))
    assert response.status_code == 413 and response.json()["code"] == "too_many_rows"


async def test_the_pass_reads_in_keyset_batches_of_the_exports_size(
    client, workspace, reporting_on, monkeypatch
):
    from backend.app.services.response_export import limits as export_limits

    assert limits.BATCH_SIZE == export_limits.BATCH_SIZE
    monkeypatch.setattr(limits, "BATCH_SIZE", 2)
    form = await make_form(workspace, survey_fields())
    await add_many(workspace, form, [dept(i) for i in range(5)])
    repo = container.report_repo()
    calls = []
    real = repo.batch

    async def spy(scope, filters, after, limit):
        calls.append((after, limit))
        return await real(scope, filters, after, limit)

    monkeypatch.setattr(repo, "batch", spy)
    result = await run(client, workspace, form, card(dimension="q:dept"))
    assert groups_of(result)["care"]["n"] == 5
    # 2, 2, 1 responses, then the empty read that ends the pass
    assert [limit for _, limit in calls] == [2, 2, 2, 2]
    assert calls[0][0] is None
    assert all(after is not None for after, _ in calls[1:])
    assert [(a.created_at, a.id) for a, _ in calls[1:]] == sorted(
        (a.created_at, a.id) for a, _ in calls[1:]
    )


async def test_responses_stored_before_they_carried_a_workspace_are_read_too(
    client, workspace, reporting_on
):
    """The second part of the scope: a form linked to this workspace only owns the
    responses stored without a workspace (#768's backfill not yet run)."""
    form = await make_form(workspace, survey_fields())
    await add_many(workspace, form, [dept(i) for i in range(3)])
    async with container.pg_sessionmaker()() as session, session.begin():
        await session.execute(
            update(FormResponseRow)
            .where(FormResponseRow.form_id == form.form_id)
            # (the column is generated from the document)
            .values(doc=FormResponseRow.doc.op("-")("workspace_id"))
        )
    await add_many(workspace, form, [dept(i) for i in range(2)])
    result = await run(client, workspace, form, card(dimension="q:dept"), card("t", "tile"))
    assert result["n"] == 5 and result["scanned"] == 5
    assert groups_of(result)["care"]["n"] == 5


# ------------------------------------------------------ deleted responses


async def test_a_deleted_response_is_in_no_report(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    docs = [
        await add_response(workspace, form, {"dept": answer_choice("care"), "score": answer_number(5)}, document=True),
        await add_response(workspace, form, {"dept": answer_choice("care"), "score": answer_number(1)}, document=True),
    ]
    body = (
        card("a", "bar", dimension="q:dept", measures=[{"agg": "count"}, {"agg": "avg", "field": "q:score"}]),
        card("t", "tile"),
        card("v", "bar", dimension="form_version"),
    )
    before = await run(client, workspace, form, *body)
    assert groups_of(before, "a")["care"]["values"] == [2, 3]
    await container.form_response_repo().delete_form_response(docs[1])
    after = await run(client, workspace, form, *body)
    assert after["n"] == 1
    assert groups_of(after, "a")["care"]["values"] == [1, 5]
    assert groups_of(after, "t")["all"]["values"] == [1]
    assert groups_of(after, "v")["1"]["n"] == 1


# --------------------------------------------------------------------- cache


class Counter:
    """How often the pass ran and how many answers it decrypted."""

    def __init__(self, monkeypatch):
        self.scans = 0
        self.decrypted = 0
        real_scan = engine_module.ReportEngine.scan
        real_answers = engine_module.stored_answers
        outer = self

        async def scan(inner, *args, **kwargs):
            outer.scans += 1
            return await real_scan(inner, *args, **kwargs)

        def answers(*args, **kwargs):
            outer.decrypted += 1
            return real_answers(*args, **kwargs)

        monkeypatch.setattr(engine_module.ReportEngine, "scan", scan)
        monkeypatch.setattr(engine_module, "stored_answers", answers)


BODY = (card("c1", "bar", dimension="q:dept"),)


async def test_the_same_report_twice_reads_the_answers_once(
    client, workspace, reporting_on, monkeypatch
):
    form = await make_form(workspace, survey_fields())
    await add_many(workspace, form, [dept(i) for i in range(3)])
    count = Counter(monkeypatch)
    first = await run(client, workspace, form, *BODY)
    second = await run(client, workspace, form, *BODY)
    assert count.scans == 1 and count.decrypted == 3
    assert first == second and first["generatedAt"] == second["generatedAt"]
    # another definition is another entry
    await run(client, workspace, form, card("b", "bar", dimension="q:remote"))
    assert count.scans == 2
    # plaintext cards are never cached: they are one cheap query
    await run(client, workspace, form, card("v", "bar", dimension="form_version"))
    assert count.scans == 2


async def test_a_new_response_invalidates_it(client, workspace, reporting_on, monkeypatch):
    form = await make_form(workspace, survey_fields())
    await add_many(workspace, form, [dept(i) for i in range(2)])
    count = Counter(monkeypatch)
    first = await run(client, workspace, form, *BODY)
    assert groups_of(first)["care"]["n"] == 2
    await add_response(workspace, form, {"dept": answer_choice("it")})
    second = await run(client, workspace, form, *BODY)
    assert count.scans == 2
    assert groups_of(second)["it"]["n"] == 1 and second["token"] != first["token"]


async def test_a_deleted_response_invalidates_it(client, workspace, reporting_on, monkeypatch):
    form = await make_form(workspace, survey_fields())
    doc = await add_response(workspace, form, {"dept": answer_choice("care")}, document=True)
    await add_response(workspace, form, {"dept": answer_choice("care")})
    count = Counter(monkeypatch)
    first = await run(client, workspace, form, *BODY)
    assert groups_of(first)["care"]["n"] == 2
    await container.form_response_repo().delete_form_response(doc)
    second = await run(client, workspace, form, *BODY)
    assert count.scans == 2 and groups_of(second)["care"]["n"] == 1


async def test_an_edited_response_invalidates_it(client, workspace, reporting_on, monkeypatch):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    count = Counter(monkeypatch)
    await run(client, workspace, form, *BODY)
    repo = container.form_response_repo()
    stored = (await repo.list_by_form_id(await _scope(workspace, form)))[0]
    await repo.save_document(stored)  # a save moves updated_at, as an edit does
    await run(client, workspace, form, *BODY)
    assert count.scans == 2


async def _scope(workspace, form):
    from tests.app.response_helpers import form_scope

    return await form_scope(form.form_id, workspace.id)


async def test_a_changed_form_invalidates_it(client, workspace, reporting_on, monkeypatch):
    from tests.app.reporting.helpers import choice_question, republish

    form = await make_form(workspace, [choice_question("dept", {"care": "Care"}, "Dept")])
    await add_response(workspace, form, {"dept": answer_choice("care")})
    count = Counter(monkeypatch)
    first = await run(client, workspace, form, *BODY)
    assert groups_of(first)["care"]["label"] == "Care"
    await republish(workspace, form, [choice_question("dept", {"care": "Zorg"}, "Dept")])
    second = await run(client, workspace, form, *BODY)
    assert count.scans == 2 and groups_of(second)["care"]["label"] == "Zorg"


async def test_a_cached_result_is_the_callers_own_copy(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    await run(client, workspace, form, *BODY)
    entry = next(iter(container.report_service()._cache.values()))
    snapshot = repr(entry.cards)
    again = container.report_service()._cache and entry
    from backend.app.services.reporting.service import _copy

    clone = _copy(again)
    clone.cards["c1"]["groups"].clear()
    assert repr(entry.cards) == snapshot


async def test_an_answer_card_narrowed_by_deletion_status_is_never_cached(
    client, workspace, reporting_on, monkeypatch
):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    count = Counter(monkeypatch)
    for _ in range(2):
        await run(client, workspace, form, *BODY, filters={"status": ["none"]})
    assert count.scans == 2
    assert container.report_service()._cache == {} or not container.report_service()._cache


async def test_entries_hold_aggregates_only(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_response(
        workspace, form, {"dept": answer_choice(other="Very private text"), "score": answer_number(1)}
    )
    await run(client, workspace, form, *BODY, )
    for entry in container.report_service()._cache.values():
        assert "Very private text" not in repr(entry.cards)
        assert set(entry.__slots__) == {
            "token", "revision", "stored", "cards", "scanned", "unreadable", "generated_at", "matched",
        }


async def test_the_cache_is_bounded(client, workspace, reporting_on, monkeypatch):
    monkeypatch.setattr(limits, "CACHE_SIZE", 2)
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    for number in range(4):
        await run(client, workspace, form, card(f"c{number}", "bar", dimension="q:dept"))
    assert len(container.report_service()._cache) == 2


# ------------------------------------------------- the field-policy seam


class HidingScore(ReportFieldPolicy):
    def __init__(self):
        self.asked = []

    async def visible_fields(self, user, workspace_id, form_id, question_keys):
        keys = frozenset(question_keys)
        self.asked.append(keys)
        return keys - {"q:score", "q:why"}


async def test_the_policy_is_asked_by_both_routes_and_its_view_is_the_only_one_used(
    client, workspace, reporting_on, monkeypatch
):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care"), "score": answer_number(3)})
    policy = HidingScore()
    monkeypatch.setattr(container.report_service(), "_policy", policy)
    fields = await query(client, workspace, form, None, tail="fields", method="get")
    keys = {f["key"] for f in fields.json()["fields"]}
    assert "q:score" not in keys and "q:dept" in keys
    assert len(policy.asked) == 1
    # every question of the form is put to it, reportable or not
    assert {"q:score", "q:why", "q:dept"} <= policy.asked[0]
    hidden = await query(client, workspace, form, definition(card("a", "tile", measures=[{"agg": "avg", "field": "q:score"}])))
    unknown = await query(client, workspace, form, definition(card("a", "tile", measures=[{"agg": "avg", "field": "q:nope"}])))
    assert hidden.status_code == unknown.status_code == 422
    assert hidden.json() == unknown.json()
    # a hidden text question and a missing one are not told apart either
    text = await query(client, workspace, form, definition(card(dimension="q:why")))
    assert text.json() == unknown.json()
    assert len(policy.asked) == 4
    ok = await query(client, workspace, form, definition(card(dimension="q:dept")))
    assert ok.status_code == 200
    assert "score" not in str(ok.json())


async def test_two_views_of_one_form_never_share_a_cached_aggregate(
    client, workspace, reporting_on, monkeypatch
):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    count = Counter(monkeypatch)
    await run(client, workspace, form, *BODY)
    monkeypatch.setattr(container.report_service(), "_policy", HidingScore())
    await run(client, workspace, form, *BODY)
    assert count.scans == 2


def test_the_default_policy_allows_every_question():
    import asyncio as aio

    policy = ReportFieldPolicy()
    allowed = aio.run(policy.visible_fields(testUser, "w", "f", ["q:a", "q:b"]))
    assert allowed == frozenset({"q:a", "q:b"})
    assert policy.fingerprint({"q:a"}) != policy.fingerprint({"q:b"})
    assert policy.fingerprint(["q:b", "q:a"]) == policy.fingerprint(["q:a", "q:b"])


# ------------------------------------------------------- group limits


async def test_a_dimension_returns_its_biggest_groups_and_sums_the_rest(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "GROUPS_RETURNED_MAX", 2)
    form = await make_form(workspace, survey_fields())
    await add_many(
        workspace,
        form,
        [
            {"answers": {"dept": answer_choice("care")}},
            {"answers": {"dept": answer_choice("care")}},
            {"answers": {"dept": answer_choice("care")}},
            {"answers": {"dept": answer_choice("it")}},
            {"answers": {"dept": answer_choice("it")}},
            {"answers": {"dept": answer_choice("hr")}},
        ],
    )
    result = await run(client, workspace, form, card(dimension="q:dept"))
    shown = card_of(result)
    assert [g["key"] for g in shown["groups"]] == ["care", "it"]
    assert shown["otherGroups"] == {"n": 1, "count": 1}
    assert shown["truncated"] is True and "groups_truncated" in result["notices"]


async def test_a_time_axis_past_the_groups_it_keeps_says_so(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "GROUPS_KEPT_MAX", 3)
    form = await make_form(workspace, survey_fields())
    import datetime as dt

    await add_many(
        workspace,
        form,
        [{"answers": {"dept": answer_choice("care")}, "at": dt.datetime(2026, 5, d, 9, tzinfo=UTC)} for d in range(1, 8)],
    )
    result = await run(
        client, workspace, form,
        card("d", "line", dimension={"field": "submitted_at", "bucket": "day"}),
    )
    # the SQL card is not bounded by the accumulator; a scanned card is
    assert len(card_of(result, "d")["groups"]) == 7
    start = await run(
        client,
        workspace,
        await _form_with_dates(workspace, 6),
        card("s", "line", dimension={"field": "q:start", "bucket": "day"}),
    )
    shown = card_of(start, "s")
    assert len(shown["groups"]) == 3 and shown["truncated"] is True
    assert shown["otherGroups"]["count"] == 3 and shown["otherGroups"]["n"] == 3


async def _form_with_dates(workspace, days):
    from tests.app.reporting.helpers import answer_date

    form = await make_form(workspace, survey_fields(), title="Dates")
    await add_many(
        workspace,
        form,
        [{"answers": {"start": answer_date(f"2026-06-{d:02d}")}} for d in range(1, days + 1)],
    )
    return form


# ------------------------------------------------------- number semantics


async def test_sums_and_averages_are_exact_decimals(client, workspace, reporting_on):
    from tests.app.reporting.helpers import simple_question

    form = await make_form(
        workspace, [simple_question("x", "number", "X"), simple_question("calc", "calculated", "Calc")]
    )
    await add_many(
        workspace,
        form,
        [
            {"answers": {"calc": {"type": "number", "number": 0.1}, "x": answer_number(1)}},
            {"answers": {"calc": {"type": "number", "number": 0.2}, "x": answer_number(2)}},
            {"answers": {"calc": {"type": "boolean", "boolean": True}, "x": answer_number(2)}},
        ],
    )
    result = await run(
        client,
        workspace,
        form,
        card("c", "tile", measures=[{"agg": "sum", "field": "q:calc"}, {"agg": "avg", "field": "q:calc"}, {"agg": "max", "field": "q:calc"}]),
        card("x", "tile", measures=[{"agg": "avg", "field": "q:x"}]),
        card("b", "bar", dimension="q:calc"),
    )
    # 0.1 + 0.2 is 0.3, not 0.30000000000000004; a yes/no is no number
    assert groups_of(result, "c")["all"]["values"] == [0.3, 0.15, 0.2]
    assert groups_of(result, "c")["all"]["valueN"] == [2, 2, 2]
    assert groups_of(result, "x")["all"]["values"] == [1.67]
    # a calculated yes/no groups; a calculated number gives no group
    assert {k: g["n"] for k, g in groups_of(result, "b").items()} == {"yes": 1, "no": 0}


async def test_a_currency_answer_in_another_currency_is_not_added(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_many(
        workspace,
        form,
        [
            {"answers": {"fee": answer_currency("10.00", "EUR")}},
            {"answers": {"fee": answer_currency("99.00", "USD")}},
            {"answers": {"fee": {"type": "currency", "currency": {"code": "EUR", "amount": "abc"}}}},
            {"answers": {"fee": answer_currency("5.50", "EUR")}},
        ],
    )
    result = await run(
        client, workspace, form,
        card("f", "tile", measures=[{"agg": "sum", "field": "q:fee"}, {"agg": "min", "field": "q:fee"}]),
    )
    assert groups_of(result, "f")["all"]["values"] == [15.5, 5.5]
    assert groups_of(result, "f")["all"]["valueN"] == [2, 2]


async def test_booleans_and_odd_numbers_are_no_numbers(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_many(
        workspace,
        form,
        [
            {"answers": {"age": {"type": "number", "number": True}}},
            {"answers": {"age": {"type": "number", "number": "7"}}},
            {"answers": {"age": answer_number(10)}},
        ],
    )
    result = await run(
        client, workspace, form, card("a", "tile", measures=[{"agg": "sum", "field": "q:age"}])
    )
    assert groups_of(result, "a")["all"]["values"] == [17]


# ------------------------------------------------------ unreadable answers


async def test_an_answer_that_cannot_be_read_is_skipped_and_noticed(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    stored = [
        await add_response(workspace, form, {"dept": answer_choice("care")}, document=True),
        await add_response(workspace, form, {"dept": answer_choice("care")}, document=True),
    ]
    garbage = base64.b64encode(b"v1:not a ciphertext").decode()
    async with container.pg_sessionmaker()() as session, session.begin():
        await session.execute(
            update(FormResponseRow)
            .where(FormResponseRow.id == str(stored[1].id))
            .values(
                doc=FormResponseRow.doc.op("||")(
                    {"answers": {"$binary": {"base64": garbage, "subType": "00"}}}
                )
            )
        )
    result = await run(client, workspace, form, *BODY)
    assert groups_of(result)["care"]["n"] == 1
    assert card_of(result)["skipped"] == 1 and result["n"] == 2
    assert "unreadable_answers" in result["notices"]


# ------------------------------------- deletion requests and feedback


async def test_the_deletion_request_and_feedback_built_ins_count_and_filter(
    client, workspace, reporting_on
):
    form = await make_form(workspace, survey_fields())
    repo = container.form_response_repo()
    a = await add_response(workspace, form, {"dept": answer_choice("care")}, document=True)
    b = await add_response(workspace, form, {"dept": answer_choice("it")}, document=True)
    await add_response(workspace, form, {"dept": answer_choice("it")})
    await repo.add_deletion_request(a, a.response_id)
    await repo.add_respondent_feedback(b, RespondentFeedback(id="f1", status="Selected"))
    await repo.add_respondent_feedback(b, RespondentFeedback(id="f2", status="Rejected"))
    result = await run(
        client, workspace, form,
        card("s", "bar", dimension="status"),
        card("f", "bar", dimension="feedback_status"),
    )
    assert {k: g["n"] for k, g in groups_of(result, "s").items()} == {
        "none": 2, "pending": 1, "declined": 0, "success": 0,
    }
    # the newest entry's status; the rest have none
    assert {k: g["n"] for k, g in groups_of(result, "f").items()} == {"Rejected": 1, "none": 2}
    narrowed = await run(
        client, workspace, form, card("d", "bar", dimension="q:dept"), filters={"status": ["pending"]}
    )
    assert narrowed["n"] == 1 and groups_of(narrowed, "d")["care"]["n"] == 1
    none = await run(
        client, workspace, form, card("d", "bar", dimension="q:dept"), filters={"status": ["none"]}
    )
    assert none["n"] == 2 and groups_of(none, "d")["it"]["n"] == 2


async def test_source_counts_an_api_response_and_a_csv_import_apart(
    client, workspace, reporting_on
):
    from common.models.standard_form import StandardFormResponse, SubmissionSource

    form = await make_form(workspace, survey_fields())
    repo = container.form_response_repo()
    await add_response(workspace, form, {"dept": answer_choice("care")})
    await repo.save_form_response(
        form_id=form.form_id,
        response=StandardFormResponse(answers={"dept": answer_choice("it")}, form_version=1),
        workspace_id=workspace.id,
        source=SubmissionSource(key_id="k1", key_name="A key"),
    )
    result = await run(client, workspace, form, card("o", "donut", dimension="source"))
    assert {k: g["n"] for k, g in groups_of(result, "o").items()} == {"form": 1, "api": 1, "csv": 0}
    # a scanned card sees the same source
    both = await run(client, workspace, form, card("o", "donut", dimension="source", measures=[
        {"agg": "count"}, {"agg": "avg", "field": "q:age"}]))
    assert {k: g["n"] for k, g in groups_of(both, "o").items()} == {"form": 1, "api": 1, "csv": 0}


# --------------------------------------------------------------- limiter


async def test_the_rate_limit_answers_429_with_retry_after(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "REQUESTS_PER_WINDOW", 2)
    form = await make_form(workspace, survey_fields())
    for _ in range(2):
        assert (await query(client, workspace, form, definition(card()))).status_code == 200
    third = await query(client, workspace, form, definition(card()))
    assert third.status_code == 429 and third.json()["code"] == "rate_limited"
    assert int(third.headers["retry-after"]) >= 1


async def test_too_many_passes_at_once_answer_429_and_cards_in_sql_do_not_wait(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "PASS_WAIT_SECONDS", 0.05)
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    service = container.report_service()
    monkeypatch.setattr(service, "_passes", asyncio.Semaphore(0))
    busy = await query(client, workspace, form, definition(card(dimension="q:dept")))
    assert busy.status_code == 429 and busy.json()["code"] == "report_busy"
    plain = await query(client, workspace, form, definition(card(dimension="form_version")))
    assert plain.status_code == 200


async def test_every_answer_is_no_store(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    ok = await query(client, workspace, form, definition(card()))
    assert ok.headers["cache-control"] == "no-store"


async def test_no_result_holds_a_response_id_an_identity_or_answer_text(
    client, workspace, reporting_on
):
    form = await make_form(workspace, survey_fields())
    ids = [
        await add_response(
            workspace,
            form,
            {"dept": answer_choice("care", other="Hello private text"), "why": {"type": "text", "text": "free text answer"}},
            identified=True,
        )
        for _ in range(2)
    ]
    response = await query(
        client,
        workspace,
        form,
        definition(
            card("a", "bar", dimension="q:dept"),
            card("r", "donut", dimension="respondent"),
            card("t", "tile"),
        ),
    )
    text = response.text
    for ident in ids:
        assert ident not in text
    assert "person-" not in text and "example.org" not in text
    assert "free text answer" not in text and "Hello private text" not in text
    assert str(workspace.id) not in text.replace(form.form_id, "")


# --------------------------------------------- numbers, time budget, replicas


async def test_a_number_too_large_to_average_is_a_notice_not_a_500(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"age": answer_number(30)})
    # 1e30 is accepted as a number, but its average cannot be rounded to two places
    await add_response(workspace, form, {"age": answer_number(1e30)})
    # a magnitude no amount has is not a number at all
    await add_response(workspace, form, {"age": answer_number("1e9999")})
    response = await query(
        client, workspace, form,
        definition(
            card("a", "tile", measures=[{"agg": "avg", "field": "q:age"}, {"agg": "max", "field": "q:age"}]),
            card("n", "tile", measures=[{"agg": "min", "field": "q:age"}]),
        ),
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert "unreadable_answers" in result["notices"]
    values = groups_of(result, "a")["all"]["values"]
    assert values[0] is None and values[1] == 10**30
    assert groups_of(result, "n")["all"]["values"] == [30]


async def in_flight_passes() -> int:
    """The passes counted among the replicas now (reads the counter, adds none)."""
    from backend.app.services.reporting import service as service_module

    verdict = await container.rate_limiter().hit(
        service_module.SLOT_SCOPE,
        service_module.SLOT_CLIENT,
        limits.PASSES_ACROSS_REPLICAS,
        limits.PASS_SLOTS_WINDOW_SECONDS,
        amount=0,
    )
    return verdict.count


async def test_a_pass_over_its_time_budget_is_stopped_and_gives_its_places_back(
    client, workspace, reporting_on, monkeypatch
):
    monkeypatch.setattr(limits, "PASS_SECONDS", 0.05)
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    service = container.report_service()

    async def stuck(*args, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(service._engine, "scan", stuck)
    slow = await query(client, workspace, form, definition(card(dimension="q:dept")))
    assert slow.status_code == 503 and slow.json()["code"] == "report_timeout"
    # the process slot and the replicas' place are free again
    assert service._passes._value == limits.PASSES_AT_ONCE
    assert await in_flight_passes() == 0


async def test_passes_in_other_replicas_count_against_this_one(client, workspace, reporting_on):
    from backend.app.services.reporting import service as service_module

    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    limiter = container.rate_limiter()
    # as many passes in flight elsewhere as the replicas together may run
    for _ in range(limits.PASSES_ACROSS_REPLICAS):
        verdict = await limiter.admit(
            service_module.SLOT_SCOPE, service_module.SLOT_CLIENT,
            limits.PASSES_ACROSS_REPLICAS, limits.PASS_SLOTS_WINDOW_SECONDS,
        )
        assert verdict.allowed
    busy = await query(client, workspace, form, definition(card(dimension="q:dept")))
    assert busy.status_code == 429 and busy.json()["code"] == "report_busy"
    assert int(busy.headers["retry-after"]) >= 1
    # a refused pass took no place of its own, and counts in SQL do not need one
    assert await in_flight_passes() == limits.PASSES_ACROSS_REPLICAS
    assert (await query(client, workspace, form, definition(card(dimension="form_version")))).status_code == 200
    # a place given back lets the next one in, and a finished pass leaves none held
    await limiter.release(
        service_module.SLOT_SCOPE, service_module.SLOT_CLIENT, limits.PASS_SLOTS_WINDOW_SECONDS
    )
    ok = await query(client, workspace, form, definition(card(dimension="q:dept")))
    assert ok.status_code == 200
    assert await in_flight_passes() == limits.PASSES_ACROSS_REPLICAS - 1
