"""The definition is validated strictly: allowed field types only, never a text
answer, an identity or a typed "Other" as a dimension, a filter or a value."""

import copy
import json

import pytest

from backend.app.exceptions import HTTPException
from backend.app.services.reporting import definition as defs
from backend.app.services.reporting import limits
from backend.app.services.reporting.catalogue import build_catalogue
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import cookies
from tests.app.reporting.helpers import (
    add_response,
    answer_choice,
    card,
    definition,
    make_form,
    page,
    query,
    survey_fields,
)

pytestmark = pytest.mark.asyncio

FORM = {"builder_version": "v2", "fields": page(survey_fields())}
CATALOGUE = build_catalogue([], FORM)


def refused(body, catalogue=CATALOGUE):
    """The ``(status, code)`` a definition is refused with."""
    with pytest.raises(HTTPException) as error:
        defs.validate(defs.parse(json.dumps(body).encode()), catalogue)
    return error.value.status_code, error.value.content["code"]


def accepted(body, catalogue=CATALOGUE):
    return defs.validate(defs.parse(json.dumps(body).encode()), catalogue)


def test_a_plain_definition_is_accepted():
    plan = accepted(
        definition(
            card("a", "bar", dimension="q:dept"),
            card("b", "tile", measures=[{"agg": "avg", "field": "q:score"}]),
            card("c", "line", dimension={"field": "submitted_at", "bucket": "week"}),
            filters={"formVersion": [1, 2], "respondent": "known", "status": ["none"]},
            tz="Europe/Amsterdam",
        )
    )
    assert [c.needs_answers for c in plan.cards] == [True, True, False]
    assert plan.scan_cards[0].id == "a" and plan.sql_cards[0].id == "c"


@pytest.mark.parametrize("question", ["why", "age", "fee"])
def test_a_text_or_unsuitable_question_is_never_a_dimension(question):
    # text: its type is not reportable at all; a number and an amount are
    # measures, not groups
    assert refused(definition(card(dimension=f"q:{question}"))) == (422, defs.NOT_REPORTABLE)


@pytest.mark.parametrize("question", ["dept", "tools", "score", "remote", "start"])
def test_a_choice_a_rating_a_yes_no_and_a_date_may_be_a_dimension(question):
    assert accepted(definition(card(dimension=f"q:{question}")))


def test_text_questions_and_the_personal_kinds_are_refused_everywhere():
    fields = survey_fields() + [
        {"id": "mail", "type": "email", "title": "Mail", "properties": {}},
        {"id": "tel", "type": "phone_number", "title": "Phone", "properties": {}},
        {"id": "adr", "type": "address", "title": "Address", "properties": {}},
        {"id": "sig", "type": "signature", "title": "Signed", "properties": {}},
        {"id": "doc", "type": "file_upload", "title": "File", "properties": {}},
        {"id": "tags", "type": "tags", "title": "Tags", "properties": {}},
        {"id": "own", "type": "short_text", "title": "Own", "properties": {}, "internal": True},
    ]
    catalogue = build_catalogue([], {"builder_version": "v2", "fields": page(fields)})
    for question in ("why", "mail", "tel", "adr", "sig", "doc", "tags", "own"):
        key = f"q:{question}"
        assert refused(definition(card(dimension=key)), catalogue) == (422, defs.NOT_REPORTABLE), key
        assert refused(
            definition(card("m", "tile", measures=[{"agg": "avg", "field": key}])), catalogue
        ) in ((422, defs.NOT_REPORTABLE), (422, defs.OP_NOT_ALLOWED)), key
    assert {f.key for f in catalogue.fields} == {
        "q:dept", "q:tools", "q:score", "q:age", "q:remote", "q:start", "q:fee",
    }


def test_there_is_no_text_filter_and_no_filter_on_an_answer_in_this_version():
    for filters in (
        {"where": [{"field": "q:why", "op": "contains", "value": "x"}]},
        {"search": "someone@example.org"},
        {"q:dept": "care"},
        {"respondent": "someone@example.org"},
    ):
        assert refused(definition(card(), filters=filters))[1] == defs.INVALID, filters


def test_an_identity_is_no_field():
    for key in ("respondent_email", "data_owner_identifier", "responder", "response_id", "q:"):
        assert refused(definition(card(dimension=key)))[1] == defs.UNKNOWN_FIELD, key
    # "respondent" is the kind (anonymous or identified), never who
    plan = accepted(definition(card(dimension="respondent")))
    assert plan.cards[0].dimension.builtin == "respondent"


def test_an_unknown_question_and_a_hidden_one_are_the_same_answer():
    visible = CATALOGUE.restricted_to({"q:dept"})
    unknown = refused(definition(card(dimension="q:nope")), visible)
    hidden = refused(definition(card(dimension="q:score")), visible)
    assert unknown == hidden == (422, defs.UNKNOWN_FIELD)
    for body in (definition(card(dimension="q:nope")), definition(card(dimension="q:score"))):
        with pytest.raises(HTTPException) as error:
            defs.validate(defs.parse(json.dumps(body).encode()), visible)
        assert error.value.content["message"] == "No such question in this form."
    # a hidden text question is not told apart from a missing one either
    text = refused(definition(card(dimension="q:why")), visible)
    assert text == (422, defs.UNKNOWN_FIELD)


def test_only_suitable_aggregates_are_allowed():
    assert refused(definition(card("a", "tile", measures=[{"agg": "sum", "field": "q:score"}])))[1] == defs.OP_NOT_ALLOWED
    assert refused(definition(card("a", "tile", measures=[{"agg": "avg", "field": "q:dept"}])))[1] == defs.OP_NOT_ALLOWED
    assert refused(definition(card("a", "tile", measures=[{"agg": "avg", "field": "submitted_at"}])))[1] == defs.OP_NOT_ALLOWED
    assert refused(definition(card("a", "tile", measures=[{"agg": "count", "field": "q:score"}])))[1] == defs.INVALID
    assert refused(definition(card("a", "tile", measures=[{"agg": "avg"}])))[1] == defs.INVALID
    assert refused(definition(card("a", "tile", measures=[{"agg": "median", "field": "q:score"}])))[1] == defs.INVALID
    # numbers only (a number question can be summed, a rating cannot)
    assert accepted(definition(card("a", "tile", measures=[{"agg": "sum", "field": "q:age"}])))


def test_the_status_dimensions_only_count():
    assert refused(
        definition(card("a", "bar", dimension="status", measures=[{"agg": "avg", "field": "q:score"}]))
    ) == (422, defs.OP_NOT_ALLOWED)
    assert refused(
        definition(card("a", "bar", dimension="feedback_status", measures=[{"agg": "avg", "field": "q:score"}]))
    ) == (422, defs.OP_NOT_ALLOWED)


def test_a_card_kind_has_to_suit_its_data():
    assert refused(definition(card("a", "tile", dimension="q:dept")))[1] == defs.INVALID
    assert refused(definition(card("a", "bar")))[1] == defs.INVALID
    assert refused(definition(card("a", "line", dimension="q:dept")))[1] == defs.INVALID
    assert refused(definition(card("a", "donut", dimension="q:tools")))[1] == defs.INVALID
    assert refused(definition(card("a", "donut", dimension="submitted_at")))[1] == defs.INVALID
    assert accepted(definition(card("a", "donut", dimension="q:remote")))
    assert accepted(definition(card("a", "line", dimension="q:start")))


def test_a_donut_of_more_than_six_groups_is_refused():
    many = {f"o{i}": f"Option {i}" for i in range(7)}
    from tests.app.reporting.helpers import choice_question

    catalogue = build_catalogue(
        [], {"builder_version": "v2", "fields": page([choice_question("big", many)])}
    )
    assert refused(definition(card("a", "donut", dimension="q:big")), catalogue)[1] == defs.INVALID
    assert accepted(definition(card("a", "bar", dimension="q:big")), catalogue)


def test_a_bucket_only_applies_to_a_date():
    assert refused(definition(card(dimension={"field": "q:dept", "bucket": "day"})))[1] == defs.INVALID
    assert accepted(definition(card("a", "line", dimension={"field": "q:start", "bucket": "month"})))


def test_extra_keys_wrong_types_and_versions_are_refused():
    base = definition(card())
    for body in (
        {**base, "v": 2},
        {**base, "extra": 1},
        {**base, "cards": []},
        {**base, "tz": "Mars/Phobos"},
        {**base, "filters": {"submittedFrom": "2026-05-01", "formVersion": ["x"]}},
        {**base, "filters": {"formVersion": [-1]}},
        {**base, "filters": {"submittedFrom": "2026-05-02T00:00:00Z", "submittedTo": "2026-05-01T00:00:00Z"}},
        {**base, "cards": [{**card(), "extra": True}]},
        {**base, "cards": [{**card(), "id": "bad id!"}]},
        {**base, "cards": [{**card(), "measures": []}]},
        {**base, "cards": [card("a"), card("a")]},
        {**base, "cards": [{**card(), "title": "x" * 81}]},
    ):
        assert refused(body)[0] == 422, body


def test_the_sizes_are_bounded():
    too_many_cards = definition(*[card(f"c{i}") for i in range(limits.CARDS_MAX + 1)])
    assert refused(too_many_cards)[1] == defs.INVALID
    assert accepted(definition(*[card(f"c{i}") for i in range(limits.CARDS_MAX)]))
    many_measures = card("m", "table", measures=[{"agg": "count"}] * (limits.MEASURES_MAX + 1))
    assert refused(definition(many_measures))[1] == defs.INVALID
    with pytest.raises(HTTPException) as error:
        defs.parse(b" " * (limits.DEFINITION_MAX_BYTES + 1))
    assert error.value.content["code"] == defs.INVALID


def test_the_message_names_where_never_the_value():
    with pytest.raises(HTTPException) as error:
        defs.parse(json.dumps(definition(card(), filters={"respondent": "secret@example.org"})).encode())
    message = error.value.content["message"]
    assert "filters.respondent" in message and "secret@example.org" not in message


def test_the_hash_is_the_same_for_the_same_definition_in_another_key_order():
    a = defs.parse(json.dumps({"v": 1, "cards": [card()]}).encode())
    b = defs.parse(json.dumps({"cards": [dict(reversed(list(card().items())))], "v": 1}).encode())
    assert a.digest() == b.digest()
    c = defs.parse(json.dumps({"v": 1, "cards": [card("other")]}).encode())
    assert a.digest() != c.digest()


async def test_the_route_answers_these_codes(client, workspace, reporting_on):
    form = await make_form(workspace, survey_fields())
    await add_response(workspace, form, {"dept": answer_choice("care")})
    for body, status, code in (
        (definition(card(dimension="q:why")), 422, "field_not_reportable"),
        (definition(card(dimension="q:nope")), 422, "unknown_field"),
        (definition(card("x", "tile", measures=[{"agg": "sum", "field": "q:score"}])), 422, "op_not_allowed"),
        ({"v": 1}, 422, "invalid_definition"),
    ):
        response = await query(client, workspace, form, body)
        assert response.status_code == status and response.json()["code"] == code, response.text
    big = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/report/query",
        content=b"{" + b" " * (limits.DEFINITION_MAX_BYTES + 10) + b"}",
        headers={"content-type": "application/json"},
        cookies=cookies(testUser),
    )
    assert big.status_code == 422 and big.json()["code"] == "invalid_definition"


async def test_the_catalogue_route_lists_what_may_be_used_and_nothing_else(
    client, workspace, reporting_on
):
    form = await make_form(workspace, survey_fields())
    response = await query(client, workspace, form, None, tail="fields", method="get")
    assert response.status_code == 200
    body = response.json()
    assert response.headers["cache-control"] == "no-store"
    keys = {f["key"] for f in body["fields"]}
    assert keys == {"q:dept", "q:tools", "q:score", "q:age", "q:remote", "q:start", "q:fee"}
    dept = next(f for f in body["fields"] if f["key"] == "q:dept")
    assert dept["kind"] == "choice" and dept["dimension"] is True
    assert [o["label"] for o in dept["options"]] == ["Care", "IT", "HR"]
    assert {b["key"] for b in body["builtins"]} >= {"submitted_at", "form_version", "respondent"}
    assert body["limits"]["maxRows"] == limits.REPORT_MAX_ROWS
    assert "Why" not in json.dumps(body)
