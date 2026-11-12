"""Conditions on answers (``filters.where``): which responses a report is about,
by what they answered. Option ids, numbers, yes/no and dates only, each checked
against the question (never free text); every card then counts the responses
that met all of them, in the same pass; a question the caller may not use is
refused as one that does not exist."""

import pytest

from backend.app.container import container
from backend.app.services.reporting import limits
from backend.app.services.reporting.policy import ReportFieldPolicy
from tests.app.reporting.helpers import (
    add_response,
    answer_bool,
    answer_choice,
    answer_choices,
    answer_currency,
    answer_date,
    answer_number,
    answer_text,
    card,
    card_of,
    definition,
    groups_of,
    make_form,
    query,
    survey_fields,
)

pytestmark = pytest.mark.asyncio


async def seeded(workspace):
    """Eight responses: department, tools, score, age, remote, start, fee, why."""
    form = await make_form(workspace, survey_fields())
    rows = [
        {"dept": answer_choice("care"), "tools": answer_choices("mail", "chat"), "score": answer_number(5), "age": answer_number(30), "remote": answer_bool(True), "start": answer_date("2026-03-01"), "fee": answer_currency("10.00"), "why": answer_text("Ada said so")},
        {"dept": answer_choice("care"), "tools": answer_choices("mail"), "score": answer_number(4), "age": answer_number(41), "remote": answer_bool(False), "start": answer_date("2026-03-15"), "fee": answer_currency("25.50")},
        {"dept": answer_choice("it"), "tools": answer_choices("chat", "wiki"), "score": answer_number(2), "age": answer_number(25), "remote": answer_bool(True), "start": answer_date("2026-04-02")},
        {"dept": answer_choice("it"), "tools": answer_choices("wiki"), "score": answer_number(5), "age": answer_number(52), "start": answer_date("2026-05-20"), "fee": answer_currency("5")},
        {"dept": answer_choice("hr"), "score": answer_number(3), "age": answer_number(30), "remote": answer_bool(False)},
        {"dept": answer_choice(other="Kitchen"), "tools": answer_choices("mail", "chat", "wiki"), "age": answer_number(19)},
        {"score": answer_number(1)},
        {},
    ]
    for answers in rows:
        await add_response(workspace, form, answers)
    return form


async def run(client, workspace, form, *where, cards=None, user=None, **extra):
    body = definition(*(cards or [card("t", "tile")]), filters={"where": list(where)}, **extra)
    kwargs = {} if user is None else {"user": user}
    return await query(client, workspace, form, body, **kwargs)


async def count(client, workspace, form, *where):
    response = await run(client, workspace, form, *where)
    assert response.status_code == 200, response.text
    return response.json()["n"]


@pytest.mark.parametrize(
    "clause,expected",
    [
        ({"field": "q:dept", "op": "is", "value": "care"}, 2),
        ({"field": "q:dept", "op": "is_not", "value": "care"}, 4),  # answered, and not care (it, it, hr, other)
        ({"field": "q:dept", "op": "any_of", "value": ["care", "hr"]}, 3),
        ({"field": "q:dept", "op": "is_empty"}, 2),
        ({"field": "q:dept", "op": "is_not_empty"}, 6),
        ({"field": "q:tools", "op": "has_any", "value": ["wiki"]}, 3),
        ({"field": "q:tools", "op": "has_all", "value": ["mail", "chat"]}, 2),
        ({"field": "q:tools", "op": "is_empty"}, 3),
        ({"field": "q:score", "op": ">=", "value": 4}, 3),
        ({"field": "q:score", "op": "=", "value": 5}, 2),
        ({"field": "q:score", "op": "!=", "value": 5}, 4),  # answered a score other than 5
        ({"field": "q:score", "op": "between", "value": [2, 4]}, 3),
        ({"field": "q:score", "op": "is_empty"}, 2),
        ({"field": "q:age", "op": "<", "value": 30}, 2),
        ({"field": "q:age", "op": "<=", "value": 30}, 4),
        ({"field": "q:age", "op": ">", "value": 40.5}, 2),
        ({"field": "q:remote", "op": "is", "value": True}, 2),
        ({"field": "q:remote", "op": "is", "value": False}, 2),
        ({"field": "q:remote", "op": "is_empty"}, 4),
        ({"field": "q:start", "op": "before", "value": "2026-03-15"}, 1),
        ({"field": "q:start", "op": "after", "value": "2026-03-15"}, 2),
        ({"field": "q:start", "op": "between", "value": ["2026-03-01", "2026-04-02"]}, 3),
        ({"field": "q:start", "op": "is_not_empty"}, 4),
        ({"field": "q:fee", "op": ">", "value": 9.99}, 2),
        ({"field": "q:fee", "op": "between", "value": [5, 10]}, 2),
    ],
)
async def test_each_operator_keeps_the_responses_that_meet_it(client, workspace, reporting_on, clause, expected):
    form = await seeded(workspace)
    assert await count(client, workspace, form, clause) == expected


async def test_every_condition_must_be_met(client, workspace, reporting_on):
    form = await seeded(workspace)
    both = [{"field": "q:dept", "op": "is", "value": "it"}, {"field": "q:score", "op": ">=", "value": 3}]
    assert await count(client, workspace, form, *both) == 1
    assert await count(client, workspace, form) == 8


async def test_every_card_is_about_the_responses_that_met_them_the_sql_ones_too(client, workspace, reporting_on):
    form = await seeded(workspace)
    where = {"field": "q:dept", "op": "is", "value": "care"}
    response = await run(
        client, workspace, form, where,
        cards=[
            card("t", "tile"),
            card("tools", "bar", dimension="q:tools"),
            card("ver", "bar", dimension="form_version"),
            card("avg", "tile", measures=[{"agg": "avg", "field": "q:age"}]),
        ],
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["n"] == 2 and result["scanned"] == 8
    assert groups_of(result, "t")["all"]["n"] == 2
    assert groups_of(result, "tools")["mail"]["n"] == 2 and groups_of(result, "tools")["wiki"]["n"] == 0
    # a card on a plaintext column answers from the same pass: only the 2 are counted
    assert sum(g["n"] for g in groups_of(result, "ver").values()) == 2
    assert groups_of(result, "avg")["all"]["values"] == [35.5]
    assert card_of(result, "t")["answered"] == 2


async def test_the_plaintext_filters_and_the_conditions_narrow_together(client, workspace, reporting_on):
    form = await seeded(workspace)
    body = definition(card("t", "tile"), filters={"respondent": "known", "where": [{"field": "q:score", "op": "is_empty"}]})
    result = (await query(client, workspace, form, body)).json()
    # nobody was identified: the plaintext filter alone empties it
    assert result["n"] == 0


async def test_a_response_whose_answers_cannot_be_read_meets_nothing(client, workspace, reporting_on):
    from sqlalchemy import update

    from backend.db.models import FormResponseRow

    form = await seeded(workspace)
    stored = await add_response(workspace, form, {"dept": answer_choice("care")}, document=True)
    async with container.pg_sessionmaker()() as session, session.begin():
        await session.execute(
            update(FormResponseRow)
            .where(FormResponseRow.id == str(stored.id))
            .values(doc=FormResponseRow.doc.op("||")({"answers": {"$binary": {"base64": "bm90IGEgY2lwaGVydGV4dA==", "subType": "00"}}}))
        )
    result = (await run(client, workspace, form, {"field": "q:dept", "op": "is", "value": "care"})).json()
    assert result["n"] == 2 and "unreadable_answers" in result["notices"]


async def test_a_different_condition_is_a_different_result_and_the_cache_does_not_mix_them(client, workspace, reporting_on):
    form = await seeded(workspace)
    care = {"field": "q:dept", "op": "is", "value": "care"}
    it = {"field": "q:dept", "op": "is", "value": "it"}
    first = (await run(client, workspace, form, care)).json()
    other = (await run(client, workspace, form, it, cards=[card("t", "tile")])).json()
    again = (await run(client, workspace, form, care)).json()
    assert first["n"] == 2 and other["n"] == 2 and again["generatedAt"] == first["generatedAt"]
    third = (await run(client, workspace, form, {"field": "q:dept", "op": "is", "value": "hr"})).json()
    assert third["n"] == 1


async def test_a_new_response_changes_the_figures_of_a_filtered_report(client, workspace, reporting_on):
    form = await seeded(workspace)
    care = {"field": "q:dept", "op": "is", "value": "care"}
    assert (await run(client, workspace, form, care)).json()["n"] == 2
    await add_response(workspace, form, {"dept": answer_choice("care")})
    assert (await run(client, workspace, form, care)).json()["n"] == 3


# ----------------------------------------------------------------- refusals


@pytest.mark.parametrize(
    "clause,code",
    [
        # no such question, a question that is no filter (text), and a built-in
        ({"field": "q:nope", "op": "is", "value": "x"}, "unknown_field"),
        ({"field": "q:why", "op": "is_empty"}, "field_not_reportable"),
        ({"field": "form_version", "op": "=", "value": 1}, "field_not_reportable"),
        # an operator the kind does not take
        ({"field": "q:dept", "op": ">", "value": 1}, "op_not_allowed"),
        ({"field": "q:tools", "op": "is", "value": "mail"}, "op_not_allowed"),
        ({"field": "q:score", "op": "has_any", "value": ["a"]}, "op_not_allowed"),
        ({"field": "q:remote", "op": "=", "value": True}, "op_not_allowed"),
        ({"field": "q:start", "op": "<", "value": "2026-01-01"}, "op_not_allowed"),
        # a value that does not suit
        ({"field": "q:dept", "op": "is", "value": "no-such-option"}, "invalid_definition"),
        ({"field": "q:dept", "op": "is", "value": ["care"]}, "invalid_definition"),
        ({"field": "q:dept", "op": "any_of", "value": "care"}, "invalid_definition"),
        ({"field": "q:dept", "op": "any_of", "value": []}, "invalid_definition"),
        ({"field": "q:dept", "op": "is"}, "invalid_definition"),
        ({"field": "q:dept", "op": "is_empty", "value": "care"}, "invalid_definition"),
        ({"field": "q:tools", "op": "has_any", "value": ["mail", "ghost"]}, "invalid_definition"),
        ({"field": "q:score", "op": ">", "value": "3"}, "invalid_definition"),
        ({"field": "q:score", "op": ">", "value": True}, "invalid_definition"),
        ({"field": "q:score", "op": ">", "value": 10**16}, "invalid_definition"),
        ({"field": "q:score", "op": "between", "value": [5, 1]}, "invalid_definition"),
        ({"field": "q:score", "op": "between", "value": [1]}, "invalid_definition"),
        ({"field": "q:remote", "op": "is", "value": "yes"}, "invalid_definition"),
        ({"field": "q:start", "op": "before", "value": "yesterday"}, "invalid_definition"),
        ({"field": "q:start", "op": "before", "value": "2026-13-45"}, "invalid_definition"),
        ({"field": "q:start", "op": "between", "value": ["2026-05-01", "2026-04-01"]}, "invalid_definition"),
        ({"field": "q:dept", "op": "is", "value": "x" * (limits.CLAUSE_VALUE_MAX + 1)}, "invalid_definition"),
        ({"field": "q:dept", "op": "contains", "value": "Ada"}, "invalid_definition"),
        ({"field": "q:dept", "op": "is", "value": "care", "extra": 1}, "invalid_definition"),
    ],
)
async def test_a_condition_is_checked_against_the_question_before_anything_runs(client, workspace, reporting_on, clause, code):
    form = await seeded(workspace)
    refused = await run(client, workspace, form, clause)
    assert refused.status_code == 422 and refused.json()["code"] == code, refused.text
    # the message says where, never what was sent
    assert "Ada" not in refused.text and "no-such-option" not in refused.text


async def test_there_are_at_most_ten_conditions(client, workspace, reporting_on):
    form = await seeded(workspace)
    clause = {"field": "q:score", "op": ">=", "value": 1}
    assert (await run(client, workspace, form, *[clause] * limits.CLAUSES_MAX)).status_code == 200
    refused = await run(client, workspace, form, *[clause] * (limits.CLAUSES_MAX + 1))
    assert refused.status_code == 422 and refused.json()["code"] == "invalid_definition"


async def test_a_condition_never_holds_what_a_respondent_wrote(client, workspace, reporting_on):
    """A text answer is no question to filter on, and no value is read as text: the one
    string a condition takes is an option id the question has."""
    form = await seeded(workspace)
    for clause in (
        {"field": "q:why", "op": "is", "value": "Ada said so"},
        {"field": "q:dept", "op": "is", "value": "Kitchen"},  # the typed "Other" has no option id
    ):
        refused = await run(client, workspace, form, clause)
        assert refused.status_code == 422, clause
    # but "Other" is still a group of the question, counted, its text never read
    result = (await run(client, workspace, form, {"field": "q:dept", "op": "is_not_empty"}, cards=[card("g", "bar", dimension="q:dept")])).json()
    assert groups_of(result, "g")["other"]["n"] == 1 and "Kitchen" not in str(result)


class HidingScore(ReportFieldPolicy):
    async def visible_fields(self, user, workspace_id, form_id, question_keys):
        return frozenset(question_keys) - {"q:score"}


async def test_a_question_the_caller_may_not_use_is_refused_as_one_that_does_not_exist(client, workspace, reporting_on, monkeypatch):
    form = await seeded(workspace)
    hidden = await run(client, workspace, form, {"field": "q:score", "op": ">=", "value": 3})
    ghost = await run(client, workspace, form, {"field": "q:nope", "op": ">=", "value": 3})
    assert hidden.status_code == 200  # the default policy allows it
    monkeypatch.setattr(container.report_service(), "_policy", HidingScore())
    container.report_service()._catalogues.clear()
    refused = await run(client, workspace, form, {"field": "q:score", "op": ">=", "value": 3})
    assert refused.status_code == 422 and refused.json() == ghost.json()


async def test_the_catalogue_says_which_operators_each_question_takes(client, workspace, reporting_on):
    form = await seeded(workspace)
    fields = (await query(client, workspace, form, None, tail="fields", method="get")).json()["fields"]
    ops = {f["key"]: f["filterOps"] for f in fields}
    assert ops["q:dept"] == ["is", "is_not", "any_of", "is_empty", "is_not_empty"]
    assert ops["q:tools"] == ["has_any", "has_all", "is_empty", "is_not_empty"]
    assert ops["q:score"][:3] == ["=", "!=", ">"] and "between" in ops["q:score"]
    assert ops["q:remote"] == ["is", "is_empty", "is_not_empty"]
    assert ops["q:start"] == ["before", "after", "between", "is_empty", "is_not_empty"]
    assert "q:why" not in ops


async def test_the_cap_still_counts_the_plaintext_set_not_the_matches(client, workspace, reporting_on, monkeypatch):
    form = await seeded(workspace)
    monkeypatch.setattr(limits, "REPORT_MAX_ROWS", 5)
    refused = await run(client, workspace, form, {"field": "q:dept", "op": "is", "value": "hr"})
    assert refused.status_code == 413 and refused.json()["count"] == 8
