"""Option labels resolve across the versions of a form (the note's open point):
a question present in several versions is one entry by its id; the newest
version that has an option names it; an option only an older version has keeps
its old label; an option no version has any more is "Removed option"."""

import pytest

from backend.app.services.reporting.catalogue import build_catalogue
from tests.app.reporting.helpers import (
    add_many,
    add_response,
    answer_choice,
    answer_number,
    card,
    card_of,
    choice_question,
    definition,
    groups_of,
    make_form,
    page,
    query,
    republish,
    simple_question,
)

pytestmark = pytest.mark.asyncio


def form_dict(*questions):
    return {"builder_version": "v2", "fields": page(list(questions))}


def test_the_newest_version_names_an_option_and_an_older_only_option_keeps_its_label():
    v1 = form_dict(choice_question("q", {"a": "Apple", "b": "Banana", "c": "Cherry"}, "Fruit"))
    v2 = form_dict(choice_question("q", {"a": "Apples (fresh)", "c": "Cherry", "d": "Date"}, "Fruit?"))
    catalogue = build_catalogue([(1, v1), (2, v2)], None)
    (field,) = catalogue.fields
    # newest version's order and labels first, then the option only v1 has
    assert field.options == (
        ("a", "Apples (fresh)"), ("c", "Cherry"), ("d", "Date"), ("b", "Banana"),
    )
    assert field.label == "Fruit?"
    assert field.versions == (1, 2)


def test_a_question_only_older_versions_have_is_listed_with_its_versions():
    v1 = form_dict(simple_question("old", "rating", "Old"), simple_question("kept", "number", "Kept"))
    v2 = form_dict(simple_question("kept", "number", "Kept"))
    catalogue = build_catalogue([(1, v1), (2, v2)], v2)
    by_key = {f.key: f for f in catalogue.fields}
    assert by_key["q:old"].versions == (1,) and by_key["q:old"].in_current is False
    assert by_key["q:kept"].versions == (1, 2) and by_key["q:kept"].in_current is True
    assert by_key["q:old"].as_json()["inCurrentVersion"] is False


def test_the_draft_alone_is_enough_and_the_latest_version_is_current_without_one():
    draft = form_dict(simple_question("n", "number", "N"))
    (field,) = build_catalogue([], draft).fields
    assert field.versions == () and field.in_current is True
    (published,) = build_catalogue([(3, draft)], None).fields
    assert published.versions == (3,) and published.in_current is True


def test_a_question_that_changed_type_takes_the_newest_definition():
    v1 = form_dict(simple_question("q", "short_text", "Q"))
    v2 = form_dict(simple_question("q", "rating", "Q"))
    catalogue = build_catalogue([(1, v1), (2, v2)], None)
    assert [f.kind for f in catalogue.fields] == ["scale"]


def test_a_choice_with_an_option_source_or_one_currency_too_many_is_not_reportable():
    sourced = choice_question("s", {"a": "A"}, "S", option_source={"kind": "list", "list_id": "x"})
    sourced["properties"]["option_source"] = {"kind": "list", "listId": "x"}
    many = simple_question("m", "currency", "M", currencies=["EUR", "USD"])
    catalogue = build_catalogue([], form_dict(sourced, many))
    assert catalogue.fields == ()
    assert catalogue.unreportable == frozenset({"q:s", "q:m"})


async def test_a_report_resolves_labels_over_published_versions(client, workspace, reporting_on):
    form = await make_form(
        workspace,
        [choice_question("fruit", {"a": "Apple", "b": "Banana"}, "Fruit"), simple_question("n", "number", "N")],
    )
    await add_many(
        workspace,
        form,
        [
            {"answers": {"fruit": answer_choice("a"), "n": answer_number(1)}, "version": 1},
            {"answers": {"fruit": answer_choice("b"), "n": answer_number(3)}, "version": 1},
        ],
    )
    # version 2: "Apple" renamed, "Banana" dropped, "Date" new
    await republish(
        workspace,
        form,
        [
            choice_question("fruit", {"a": "Apple (fresh)", "d": "Date"}, "Fruit"),
            simple_question("n", "number", "N"),
        ],
    )
    await add_many(
        workspace,
        form,
        [
            {"answers": {"fruit": answer_choice("a"), "n": answer_number(5)}, "version": 2},
            {"answers": {"fruit": answer_choice("d"), "n": answer_number(7)}, "version": 2},
            {"answers": {"fruit": answer_choice("zzz")}, "version": 2},
        ],
    )
    response = await query(
        client,
        workspace,
        form,
        definition(
            card("f", "bar", dimension="q:fruit", measures=[{"agg": "count"}, {"agg": "avg", "field": "q:n"}]),
            card("v", "bar", dimension="form_version"),
        ),
    )
    assert response.status_code == 200, response.text
    result = response.json()
    groups = groups_of(result, "f")
    # the old option under its old label, the renamed one under its new, one group
    # across both versions; an id no version has is "Removed option", never the id
    assert {k: (g["label"], g["n"]) for k, g in groups.items()} == {
        "a": ("Apple (fresh)", 2),
        "d": ("Date", 1),
        "b": ("Banana", 1),
        "removed": ("Removed option", 1),
    }
    assert [g["key"] for g in card_of(result, "f")["groups"]] == ["a", "d", "b", "removed"]
    assert groups["a"]["values"] == [2, 3]
    assert "zzz" not in response.text
    assert {k: g["n"] for k, g in groups_of(result, "v").items()} == {"1": 2, "2": 3}
    fields = await query(client, workspace, form, None, tail="fields", method="get")
    fruit = next(f for f in fields.json()["fields"] if f["key"] == "q:fruit")
    assert fruit["versions"] == [1, 2]


async def test_a_question_dropped_in_a_later_version_still_reports_its_answers(
    client, workspace, reporting_on
):
    form = await make_form(workspace, [simple_question("old", "rating", "Old"), simple_question("n", "number", "N")])
    await add_response(workspace, form, {"old": answer_number(4)}, version=1)
    await republish(workspace, form, [simple_question("n", "number", "N")])
    await add_response(workspace, form, {"n": answer_number(9)}, version=2)
    response = await query(
        client, workspace, form,
        definition(card("o", "tile", measures=[{"agg": "avg", "field": "q:old"}])),
    )
    assert response.status_code == 200
    assert groups_of(response.json(), "o")["all"]["values"] == [4]
    fields = (await query(client, workspace, form, None, tail="fields", method="get")).json()
    old = next(f for f in fields["fields"] if f["key"] == "q:old")
    assert old["versions"] == [1] and old["inCurrentVersion"] is False
