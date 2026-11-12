"""Every kind of card through the query route: counts, averages, distributions
and over-time series, over answers stored (and encrypted) as a submission does."""

import datetime as dt

import pytest

from tests.app.controllers.data import testUser
from tests.app.reporting.helpers import (
    UTC,
    add_many,
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


def day(month, d, hour=12):
    return dt.datetime(2026, month, d, hour, tzinfo=UTC)


async def seeded(workspace):
    form = await make_form(workspace, survey_fields())
    await add_many(
        workspace,
        form,
        [
            {
                "answers": {
                    "dept": answer_choice("care"),
                    "tools": answer_choices("mail", "chat"),
                    "score": answer_number(4),
                    "age": answer_number(30),
                    "remote": answer_bool(True),
                    "start": answer_date("2026-03-02"),
                    "fee": answer_currency("10.50"),
                    "why": answer_text("secret reason"),
                },
                "at": day(3, 2),
            },
            {
                "answers": {
                    "dept": answer_choice("care"),
                    "tools": answer_choices("chat"),
                    "score": answer_number(5),
                    "age": answer_number(40),
                    "remote": answer_bool(False),
                    "start": answer_date("2026-03-09"),
                    "fee": answer_currency("20.25"),
                },
                "at": day(3, 2, 18),
            },
            {
                "answers": {
                    "dept": answer_choice("it"),
                    "score": answer_number(2),
                    "age": answer_number(20),
                    "start": answer_date("2026-04-01"),
                },
                "at": day(4, 1),
                "identified": True,
                "version": 2,
            },
            {
                "answers": {"dept": answer_choice(other="Somewhere else")},
                "at": day(4, 3),
            },
            {"answers": {"dept": answer_choice("gone")}, "at": day(4, 4)},
        ],
    )
    return form


async def run(client, workspace, form, *cards, **changes):
    response = await query(client, workspace, form, definition(*cards, **changes))
    assert response.status_code == 200, response.text
    return response.json()


async def test_distribution_per_choice_counts_every_option_and_other_and_removed(
    client, workspace, reporting_on
):
    form = await seeded(workspace)
    result = await run(client, workspace, form, card(dimension="q:dept", kind="bar"))
    groups = groups_of(result)
    assert {k: g["n"] for k, g in groups.items()} == {
        "care": 2, "it": 1, "hr": 0, "other": 1, "removed": 1,
    }
    assert groups["other"]["label"] == "Other"
    assert groups["removed"]["label"] == "Removed option"
    assert groups["care"]["label"] == "Care"
    assert [g["key"] for g in card_of(result)["groups"]] == [
        "care", "it", "hr", "other", "removed",
    ]
    assert result["n"] == 5
    assert card_of(result)["answered"] == 5 and card_of(result)["skipped"] == 0
    # the typed text of "Other" is never in the result
    assert "Somewhere else" not in str(result)


async def test_a_multiple_choice_counts_a_response_in_each_option_it_chose(
    client, workspace, reporting_on
):
    form = await seeded(workspace)
    result = await run(client, workspace, form, card(dimension="q:tools"))
    groups = groups_of(result)
    assert {k: g["n"] for k, g in groups.items()} == {"mail": 1, "chat": 2, "wiki": 0}
    shown = card_of(result)
    assert shown["multiple"] is True
    # 3 of the 5 responses answered; the groups add up to more than 2
    assert shown["answered"] == 2 and shown["skipped"] == 3


async def test_average_min_max_and_the_n_behind_each_value(client, workspace, reporting_on):
    form = await seeded(workspace)
    result = await run(
        client,
        workspace,
        form,
        card(
            "avg",
            "tile",
            measures=[
                {"agg": "count"},
                {"agg": "avg", "field": "q:score"},
                {"agg": "min", "field": "q:score"},
                {"agg": "max", "field": "q:score"},
            ],
        ),
    )
    group = groups_of(result, "avg")["all"]
    assert group["n"] == 5
    # (4 + 5 + 2) / 3 = 3.67 to two places; three of the five answered
    assert group["values"] == [5, 3.67, 2, 5]
    assert group["valueN"] == [5, 3, 3, 3]
    shown = card_of(result, "avg")
    assert shown["answered"] == 3 and shown["skipped"] == 2


async def test_an_average_of_no_answers_is_null_not_zero(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    result = await run(
        client,
        workspace,
        form,
        card("a", "tile", measures=[{"agg": "avg", "field": "q:score"}]),
    )
    assert groups_of(result, "a")["all"]["values"] == [None]
    assert card_of(result, "a")["answered"] == 0


async def test_average_per_group_sum_of_numbers_and_currency(client, workspace, reporting_on):
    form = await seeded(workspace)
    result = await run(
        client,
        workspace,
        form,
        card(
            "by",
            "table",
            dimension="q:dept",
            measures=[{"agg": "avg", "field": "q:age"}, {"agg": "sum", "field": "q:age"}],
        ),
        card("fee", "tile", measures=[{"agg": "sum", "field": "q:fee"}, {"agg": "avg", "field": "q:fee"}]),
    )
    groups = groups_of(result, "by")
    assert groups["care"]["values"] == [35, 70]
    assert groups["it"]["values"] == [20, 20]
    assert groups["hr"]["values"] == [None, None]
    assert groups_of(result, "fee")["all"]["values"] == [30.75, 15.38]


async def test_yes_no_distribution(client, workspace, reporting_on):
    form = await seeded(workspace)
    result = await run(client, workspace, form, card(dimension="q:remote", kind="donut"))
    groups = groups_of(result)
    assert {k: g["n"] for k, g in groups.items()} == {"yes": 1, "no": 1}
    assert groups["yes"]["label"] == "Yes"
    assert card_of(result)["skipped"] == 3


async def test_distribution_of_a_rating(client, workspace, reporting_on):
    form = await seeded(workspace)
    result = await run(client, workspace, form, card(dimension="q:score"))
    assert [(g["key"], g["n"]) for g in card_of(result)["groups"]] == [
        ("2", 1), ("4", 1), ("5", 1),
    ]


async def test_over_time_by_day_week_and_month_in_the_given_zone(client, workspace, reporting_on):
    form = await seeded(workspace)
    by_day = await run(
        client, workspace, form, card("d", "line", dimension={"field": "submitted_at", "bucket": "day"})
    )
    assert {k: g["n"] for k, g in groups_of(by_day, "d").items()} == {
        "2026-03-02": 2, "2026-04-01": 1, "2026-04-03": 1, "2026-04-04": 1,
    }
    by_month = await run(
        client, workspace, form, card("m", "line", dimension={"field": "submitted_at", "bucket": "month"})
    )
    assert {k: g["n"] for k, g in groups_of(by_month, "m").items()} == {"2026-03": 2, "2026-04": 3}
    by_week = await run(
        client, workspace, form, card("w", "line", dimension={"field": "submitted_at", "bucket": "week"})
    )
    # weeks start on Monday: 2 March 2026 is one, 30 March the next
    assert {k: g["n"] for k, g in groups_of(by_week, "w").items()} == {
        "2026-03-02": 2, "2026-03-30": 3,
    }
    # 18:00 UTC on 2 March is 19:00 in Amsterdam; 23:30 UTC on 1 March would be 2 March there
    form_late = await make_form(workspace, survey_fields(), title="Late")
    await add_response(workspace, form_late, {"dept": answer_choice("care")}, at=day(3, 1, 23))
    zoned = await run(
        client,
        workspace,
        form_late,
        card("z", "line", dimension="submitted_at"),
        tz="Europe/Amsterdam",
    )
    assert list(groups_of(zoned, "z")) == ["2026-03-02"]
    utc = await run(client, workspace, form_late, card("z", "line", dimension="submitted_at"))
    assert list(groups_of(utc, "z")) == ["2026-03-01"]


async def test_over_time_of_a_date_answer(client, workspace, reporting_on):
    form = await seeded(workspace)
    result = await run(
        client, workspace, form, card("s", "line", dimension={"field": "q:start", "bucket": "month"})
    )
    assert {k: g["n"] for k, g in groups_of(result, "s").items()} == {"2026-03": 2, "2026-04": 1}


async def test_plaintext_cards_are_counted_without_reading_or_decrypting_anything(
    client, workspace, reporting_on, monkeypatch
):
    """Cards by day, version, ending, status, respondent kind, source and feedback
    status run in SQL: not one answer is read."""
    from backend.app.services.reporting import engine

    form = await seeded(workspace)

    def forbidden(*args, **kwargs):
        raise AssertionError("an answer was decrypted")

    monkeypatch.setattr(engine, "stored_answers", forbidden)
    result = await run(
        client,
        workspace,
        form,
        card("v", "bar", dimension="form_version"),
        card("r", "donut", dimension="respondent"),
        card("e", "bar", dimension="ending"),
        card("s", "bar", dimension="status"),
        card("f", "bar", dimension="feedback_status"),
        card("o", "donut", dimension="source"),
        card("t", "tile"),
    )
    assert {k: g["n"] for k, g in groups_of(result, "v").items()} == {"1": 4, "2": 1}
    assert {k: g["n"] for k, g in groups_of(result, "r").items()} == {"anonymous": 4, "known": 1}
    assert {k: g["n"] for k, g in groups_of(result, "e").items()} == {"none": 5}
    assert groups_of(result, "s")["none"]["n"] == 5
    assert groups_of(result, "f")["none"]["n"] == 5
    assert {k: g["n"] for k, g in groups_of(result, "o").items()} == {"form": 5, "api": 0, "csv": 0}
    assert groups_of(result, "t")["all"]["values"] == [5]
    assert result["scanned"] == 0


async def test_a_card_that_reads_answers_does_read_them(client, workspace, reporting_on):
    form = await seeded(workspace)
    result = await run(client, workspace, form, card(dimension="q:dept"))
    assert result["scanned"] == 5


async def test_endings_by_name_and_an_ending_no_version_has_is_removed(
    client, workspace, reporting_on
):
    form = await make_form(
        workspace,
        survey_fields(),
        thankyou_page=[{"id": "ending-1", "name": "Eligible"}],
    )
    await add_many(
        workspace,
        form,
        [
            {"answers": {"dept": answer_choice("care")}, "ending_id": "ending-1"},
            {"answers": {"dept": answer_choice("care")}, "ending_id": "ending-9"},
            {"answers": {"dept": answer_choice("it")}},
        ],
    )
    result = await run(client, workspace, form, card("e", "bar", dimension="ending"))
    shown = {k: g["n"] for k, g in groups_of(result, "e").items()}
    assert shown == {"ending-1": 1, "none": 1, "removed": 1}
    assert groups_of(result, "e")["ending-1"]["label"] == "Eligible"


async def test_the_plaintext_filters_narrow_every_card(client, workspace, reporting_on):
    form = await seeded(workspace)
    narrowed = await run(
        client,
        workspace,
        form,
        card("d", "bar", dimension="q:dept"),
        card("v", "bar", dimension="form_version"),
        filters={"formVersion": [1], "respondent": "anonymous"},
    )
    assert result_n(narrowed) == 4
    assert {k: g["n"] for k, g in groups_of(narrowed, "d").items()}["it"] == 0
    since = await run(
        client,
        workspace,
        form,
        card("d", "bar", dimension="q:dept"),
        filters={"submittedFrom": "2026-04-01T00:00:00Z", "submittedTo": "2026-04-04T00:00:00Z"},
    )
    assert result_n(since) == 2


def result_n(result):
    return result["n"]


async def test_logic_hidden_answers_that_are_stored_count_as_stored(client, workspace, reporting_on):
    """An answer to a question a rule hid or a jump skipped is stored and exported
    as before; a report counts it too, and never says who "saw" the question."""
    fields = survey_fields()
    fields[2]["properties"]["logic"] = {
        "action": "hide",
        "conditions": [{"field": {"id": "dept"}, "comparison": "is_equal", "value": "care"}],
    }
    form = await make_form(workspace, fields)
    await add_response(
        workspace, form, {"dept": answer_choice("care"), "score": answer_number(3)}
    )
    result = await run(
        client, workspace, form, card("s", "tile", measures=[{"agg": "avg", "field": "q:score"}])
    )
    assert groups_of(result, "s")["all"]["values"] == [3]
