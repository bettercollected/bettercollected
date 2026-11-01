"""The five newer question types (time, day, currency, date range, tags) in a
webhook: they can be mapped, a delivery carries the shape the public API
answers them in, an empty answer is ``null`` (tags: ``[]``), the test event
carries a made-up value of the same shape, and the registration body shares it.
Everything here is synthetic."""

import json

import pytest
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.services.registration import body
from backend.app.services.webhooks import payload
from backend.app.services.webhooks.service import FieldDto
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.registration.helpers import FIELDS, publish, submit
from tests.app.webhooks.helpers import make_webhook

NEW_FIELDS = [
    {"id": "at", "type": "time", "title": "Arrival"},
    {"id": "day", "type": "day", "title": "Birthday"},
    {
        "id": "price",
        "type": "currency",
        "title": "Price",
        "properties": {"currencies": ["USD", "EUR"]},
    },
    {"id": "stay", "type": "date_range", "title": "Stay"},
    {"id": "labels", "type": "tags", "title": "Labels"},
]
SOURCES = [f["id"] for f in NEW_FIELDS]

ANSWERS = {
    "at": {"type": "time", "time": "09:30"},
    "day": {"type": "date", "date": "1990-01-02"},
    "price": {"type": "currency", "currency": {"code": "EUR", "amount": "12.50"}},
    "stay": {"type": "date_range", "date_range": {"start": "2026-01-31", "end": "2026-02-03"}},
    "labels": {"type": "tags", "tags": ["alpha", "beta"]},
}
SENT = {
    "at": "09:30",
    "day": "1990-01-02",
    "price": {"code": "EUR", "amount": "12.50"},
    "stay": {"start": "2026-01-31", "end": "2026-02-03"},
    "labels": ["alpha", "beta"],
}
EMPTY = {"at": None, "day": None, "price": None, "stay": None, "labels": []}


@pytest.fixture(autouse=True)
def switched_on(webhooks_on, public_dns, monkeypatch):
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)


def form_of(fields=NEW_FIELDS):
    return StandardForm(
        builder_version="v2",
        title="t",
        fields=[{"id": "s1", "type": "slide", "properties": {"fields": fields}}],
    )


def data_of(answers, sources=SOURCES, form=None):
    return payload.build_data(
        form or form_of(), [(s, s) for s in sources], answers, None
    )


def test_all_five_types_are_mappable_questions():
    index = body.variables_of(form_of())
    assert all(index[s].supported and index[s].reason is None for s in SOURCES)
    assert [v.source for v in body.mappable(form_of())] == SOURCES


def test_each_type_is_sent_in_the_shape_the_api_answers_it():
    assert data_of(ANSWERS) == SENT
    # the body is plain JSON: the amount stays a decimal string, no float
    assert json.dumps(data_of(ANSWERS))
    assert data_of(ANSWERS)["price"]["amount"] == "12.50"


def test_unanswered_questions_are_null_and_tags_an_empty_list():
    assert data_of({}) == EMPTY
    # a slot that is there but empty reads the same
    assert data_of(
        {
            "at": {"type": "time", "time": None},
            "price": {"type": "currency", "currency": {}},
            "stay": {"type": "date_range", "date_range": {"start": None, "end": None}},
            "labels": {"type": "tags", "tags": []},
        }
    ) == EMPTY


def test_a_half_answered_currency_or_range_keeps_both_parts():
    half = {
        "price": {"type": "currency", "currency": {"code": "EUR"}},
        "stay": {"type": "date_range", "date_range": {"start": "2026-01-31"}},
    }
    assert data_of(half, ["price", "stay"]) == {
        "price": {"code": "EUR", "amount": None},
        "stay": {"start": "2026-01-31", "end": None},
    }


def test_malformed_stored_values_never_leak_into_the_body():
    odd = {
        "at": {"time": 930},
        "price": {"currency": {"code": 1, "amount": ["x"], "extra": "y"}},
        "stay": {"date_range": "2026"},
        "labels": {"tags": ["ok", 7, None, {"a": 1}]},
    }
    assert data_of(odd, ["at", "price", "stay", "labels"]) == {
        "at": None,
        "price": None,
        "stay": None,
        "labels": ["ok"],
    }


def test_the_answers_read_as_the_server_stored_them_models_too():
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel

    response = StandardFormResponseCamelModel(answers=ANSWERS)
    assert data_of(response.answers) == SENT


def test_the_sample_data_has_the_same_shapes():
    sample = payload.sample_data(form_of(), [(s, s) for s in SOURCES])
    assert sample == {
        "at": "09:30",
        "day": "2026-01-31",
        "price": {"code": "USD", "amount": "12.50"},  # the question's default currency
        "stay": {"start": "2026-01-31", "end": "2026-02-03"},
        "labels": ["example", "tags"],
    }
    # a question that offers nothing falls back to EUR; the sample is never shared state
    plain = form_of([{"id": "price", "type": "currency", "title": "P"}])
    assert payload.sample_data(plain, [("price", "price")])["price"]["code"] == "EUR"
    sample["stay"]["start"] = "changed"
    again = payload.sample_data(form_of(), [("stay", "stay")])
    assert again["stay"]["start"] == "2026-01-31"


def test_the_schema_describes_each_shape():
    values, schema = body.build_values(
        body.variables_of(form_of()), [(s, s) for s in SOURCES], ANSWERS, None, [], None
    )
    assert values == SENT
    props = schema["properties"]
    assert props["at"] == {"title": "Arrival", "type": "string", "pattern": body.TIME_PATTERN}
    assert props["day"] == {"title": "Birthday", "type": "string", "format": "date"}
    assert props["price"]["type"] == "object" and props["price"]["required"] == ["code", "amount"]
    assert props["price"]["properties"]["code"] == {"type": "string", "pattern": body.CURRENCY_CODE_PATTERN}
    assert props["price"]["properties"]["amount"]["type"] == "string"
    assert props["stay"]["properties"]["start"] == {"type": "string", "format": "date"}
    assert props["labels"] == {"title": "Labels", "type": "array", "items": {"type": "string"}}
    # unanswered: the schema says null is possible (tags are a list, never null)
    _values, empty = body.build_values(
        body.variables_of(form_of()), [(s, s) for s in SOURCES], {}, None, [], None
    )
    assert empty["properties"]["at"]["type"] == ["string", "null"]
    assert empty["properties"]["price"]["type"] == ["object", "null"]
    assert empty["properties"]["stay"]["type"] == ["object", "null"]
    assert empty["properties"]["labels"]["type"] == "array"
    # the stored values satisfy the schema this body publishes
    import re

    assert re.match(body.TIME_PATTERN, SENT["at"])
    assert re.match(body.CURRENCY_AMOUNT_PATTERN, SENT["price"]["amount"])
    assert re.match(body.CURRENCY_CODE_PATTERN, SENT["price"]["code"])


def test_a_repeating_group_carries_the_new_types_per_item():
    group = {
        "id": "trips",
        "type": "group",
        "title": "Trips",
        "properties": {
            "repeat": {"minItems": 0, "maxItems": 3, "itemLabel": "Trip"},
            "fields": [
                {"id": "stay", "type": "date_range", "title": "Stay"},
                {"id": "cost", "type": "currency", "title": "Cost"},
                {"id": "tags", "type": "tags", "title": "Tags"},
            ],
        },
    }
    form = form_of([group])
    answers = {
        "trips": {
            "type": "group",
            "items": [
                {
                    "stay": {"date_range": {"start": "2026-01-01", "end": "2026-01-02"}},
                    "cost": {"currency": {"code": "EUR", "amount": "3"}},
                    "tags": {"tags": ["x"]},
                },
                {},
            ],
        }
    }
    values, schema = body.build_values(
        body.variables_of(form), [("trips", "trips")], answers, None, [], None
    )
    assert values["trips"] == [
        {
            "stay": {"start": "2026-01-01", "end": "2026-01-02"},
            "cost": {"code": "EUR", "amount": "3"},
            "tags": ["x"],
        },
        {"stay": None, "cost": None, "tags": []},
    ]
    item = schema["properties"]["trips"]["items"]["properties"]
    assert item["cost"]["type"] == ["object", "null"] and item["tags"]["type"] == "array"


@pytest.mark.asyncio
async def test_a_webhook_with_these_questions_saves_and_a_submission_is_delivered(
    workspace, memory_jobs, tls
):
    form = await publish(workspace, fields=[*FIELDS, *NEW_FIELDS])
    listed = {
        v.source: v
        for v in await container.webhook_service().list_variables(
            workspace.id, form.form_id, testUser
        )
    }
    assert all(listed[s].supported and listed[s].reason is None for s in SOURCES)
    hook = await make_webhook(
        workspace,
        form,
        fields=[FieldDto(source=s, key=f"k_{s}") for s in SOURCES],
    )
    assert [(f.source, f.key) for f in hook.fields] == [(s, f"k_{s}") for s in SOURCES]
    response = await submit(workspace, form, {**ANSWERS})
    (log,) = [
        r
        for r in await container.action_log_repo().many()
        if r.response_id == response.response_id
    ]
    outcome = await container.webhook_service().run_delivery(str(log.id))
    assert outcome.status == "delivered"
    (request,) = tls.requests
    sent = json.loads(request.body)
    assert sent["data"] == {f"k_{s}": SENT[s] for s in SOURCES}


@pytest.mark.asyncio
async def test_the_test_event_sends_sample_values_of_these_shapes(
    workspace, memory_jobs, tls
):
    form = await publish(workspace, fields=[*FIELDS, *NEW_FIELDS])
    hook = await make_webhook(workspace, form, fields=SOURCES)
    queued = await container.webhook_service().send_test(
        workspace.id, form.form_id, hook.id, testUser
    )
    assert (await container.webhook_service().run_delivery(queued.id)).status == "delivered"
    (request,) = tls.requests
    sent = json.loads(request.body)
    assert sent["event"] == "test"
    assert sent["data"]["price"] == {"code": "USD", "amount": "12.50"}
    assert sent["data"]["labels"] == ["example", "tags"]


# ---------------------------------------------------------- review follow-ups


def test_an_empty_string_is_not_an_answer_for_date_day_and_time():
    answers = {
        "at": {"type": "time", "time": ""},
        "day": {"type": "date", "date": ""},
    }
    assert data_of(answers, ["at", "day"]) == {"at": None, "day": None}
    plain = form_of([{"id": "born", "type": "date", "title": "Born"}])
    assert data_of({"born": {"type": "date", "date": ""}}, ["born"], plain) == {"born": None}
    values, schema = body.build_values(
        body.variables_of(form_of()), [("at", "at"), ("day", "day")], answers, None, [], None
    )
    assert schema["properties"]["at"]["type"] == ["string", "null"]
    assert schema["properties"]["day"]["type"] == ["string", "null"]


@pytest.mark.parametrize(
    "answers, expected",
    [
        # a time that is not HH:MM (a trailing newline is not one either)
        ({"at": {"time": "garbage"}}, {"at": None}),
        ({"at": {"time": "24:00"}}, {"at": None}),
        ({"at": {"time": "09:30\n"}}, {"at": None}),
        ({"day": {"date": "garbage"}}, {"day": None}),
        ({"day": {"date": "2026-02-30"}}, {"day": None}),
        # a currency part that fails its own format is null, the other stays
        (
            {"price": {"currency": {"code": "https://evil.example", "amount": "1.5"}}},
            {"price": {"code": None, "amount": "1.5"}},
        ),
        ({"price": {"currency": {"code": "eur", "amount": "12.50"}}}, {"price": {"code": None, "amount": "12.50"}}),
        ({"price": {"currency": {"code": "EUR", "amount": "abc"}}}, {"price": {"code": "EUR", "amount": None}}),
        ({"price": {"currency": {"code": "EUR", "amount": "1e5"}}}, {"price": {"code": "EUR", "amount": None}}),
        ({"price": {"currency": {"code": "EUR", "amount": "12.50\n"}}}, {"price": {"code": "EUR", "amount": None}}),
        ({"price": {"currency": {"code": "nope", "amount": "x"}}}, {"price": None}),
        # a range: bad days are null; one whose end is before its start is null as a whole
        (
            {"stay": {"date_range": {"start": "2026-01-31", "end": "soon"}}},
            {"stay": {"start": "2026-01-31", "end": None}},
        ),
        ({"stay": {"date_range": {"start": "2026-02-03", "end": "2026-01-31"}}}, {"stay": None}),
        ({"stay": {"date_range": {"start": "2026-01-31", "end": "2026-01-31"}}}, {"stay": {"start": "2026-01-31", "end": "2026-01-31"}}),
    ],
)
def test_a_value_that_fails_its_own_format_is_sent_as_null(answers, expected):
    """Answers logic hid or a jump skipped are stored with only their type
    checked; what goes out still matches the published schema."""
    stored = json.loads(json.dumps(answers))
    got = data_of(answers, list(expected))
    assert got == expected
    assert answers == stored  # nothing stored is changed


def test_what_goes_out_always_validates_against_its_own_schema():
    jsonschema = pytest.importorskip("jsonschema")
    index = body.variables_of(form_of())
    mapping = [(s, s) for s in SOURCES]
    garbage = {
        "at": {"time": "garbage"},
        "day": {"date": "x"},
        "price": {"currency": {"code": "https://evil.example", "amount": "abc"}},
        "stay": {"date_range": {"start": "2026-02-03", "end": "2026-01-31"}},
        "labels": {"tags": ["ok", 7]},
    }
    half = {
        "price": {"currency": {"code": "EUR"}},
        "stay": {"date_range": {"start": "2026-01-31"}},
    }
    for answers in (ANSWERS, {}, garbage, half):
        values, schema = body.build_values(index, mapping, answers, None, [], None)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
        ).validate(values)


def test_a_currency_code_the_creator_later_removed_from_the_list_still_validates():
    jsonschema = pytest.importorskip("jsonschema")
    form = form_of([NEW_FIELDS[2]])  # offers USD and EUR
    answers = {"price": {"currency": {"code": "GBP", "amount": "3"}}}
    values, schema = body.build_values(
        body.variables_of(form), [("price", "price")], answers, None, [], None
    )
    assert values["price"] == {"code": "GBP", "amount": "3"}
    assert "enum" not in schema["properties"]["price"]["properties"]["code"]
    jsonschema.validate(values, schema)


def _group(*children):
    return {
        "id": "trips",
        "type": "group",
        "title": "Trips",
        "properties": {
            "repeat": {"minItems": 0, "maxItems": 3, "itemLabel": "Trip"},
            "fields": list(children),
        },
    }


@pytest.mark.parametrize("order", ["null_first", "answered_first"])
def test_a_group_schema_is_nullable_whichever_item_comes_last(order):
    jsonschema = pytest.importorskip("jsonschema")
    form = form_of(
        [
            _group(
                {"id": "stay", "type": "date_range", "title": "Stay"},
                {"id": "cost", "type": "currency", "title": "Cost"},
                {"id": "at", "type": "time", "title": "At"},
                {"id": "name", "type": "short_text", "title": "Name"},
            )
        ]
    )
    answered = {
        "stay": {"date_range": {"start": "2026-01-01", "end": "2026-01-02"}},
        "cost": {"currency": {"code": "EUR", "amount": "3"}},
        "at": {"time": "10:00"},
        "name": {"text": "x"},
    }
    partial = {"cost": {"currency": {"code": "EUR"}}}
    items = [{}, answered, partial] if order == "null_first" else [answered, partial, {}]
    answers = {"trips": {"type": "group", "items": items}}
    values, schema = body.build_values(
        body.variables_of(form), [("trips", "trips")], answers, None, [], None
    )
    item = schema["properties"]["trips"]["items"]["properties"]
    assert item["stay"]["type"] == ["object", "null"]
    assert item["at"]["type"] == ["string", "null"]
    assert item["cost"]["type"] == ["object", "null"]
    assert item["cost"]["properties"]["amount"]["type"] == ["string", "null"]
    assert item["cost"]["properties"]["code"]["type"] == "string"  # no item lacks one
    assert item["name"]["type"] == "string"  # text is "" not null
    jsonschema.validate(values, schema)


def test_a_group_whose_items_are_all_answered_keeps_plain_types():
    jsonschema = pytest.importorskip("jsonschema")
    form = form_of([_group({"id": "at", "type": "time", "title": "At"})])
    answers = {"trips": {"type": "group", "items": [{"at": {"time": "10:00"}}, {"at": {"time": "11:00"}}]}}
    values, schema = body.build_values(
        body.variables_of(form), [("trips", "trips")], answers, None, [], None
    )
    assert schema["properties"]["trips"]["items"]["properties"]["at"]["type"] == "string"
    jsonschema.validate(values, schema)


# ------------------------------------------------------- the email text path


def _entries(**values):
    return [(k, k.title(), v) for k, v in values.items()]


def test_a_link_in_a_tag_is_removed_from_the_respondents_copy_but_not_the_team_mail():
    from backend.app.services.email_actions import templates

    entries = _entries(labels=["see https://evil.example/pay", "www.evil.example", "plain"])
    _subject, copy = templates.render_respondent(entries, submitted_at="", language="en")
    assert "evil.example" not in copy and "https://" not in copy
    assert templates.LINK_REMOVED in copy and "plain" in copy
    # the team's mail is the creator's own audience: answers are shown as written
    team = templates.answers_block(entries, "en")
    assert "https://evil.example/pay" in team


def test_thirty_long_tags_are_capped_in_every_mail_text():
    from backend.app.services.email_actions import templates

    tags = [f"{n:02d}" + "x" * 38 for n in range(30)]  # 30 tags of 40 characters
    entries = _entries(labels=tags)
    _subject, copy = templates.render_respondent(entries, submitted_at="", language="en")
    block = templates.copy_answers_block(entries, "en")
    assert len(block) <= templates.COPY_ANSWERS_MAX and block in copy
    assert len(templates.answers_block(entries, "en")) <= templates.LABEL_MAX + templates.VALUE_MAX + 20
    body_text = templates.render(
        "{{labels}}", entries, form_title="t", submitted_at="", language="en", subject=False
    )
    assert len(body_text) <= templates.VALUE_MAX
    subject = templates.render(
        "{{labels}}", entries, form_title="t", submitted_at="", language="en", subject=True
    )
    assert len(subject) <= templates.SUBJECT_MAX and "\n" not in subject


def test_a_currency_code_that_is_a_link_never_reaches_a_mail():
    from backend.app.services.email_actions import templates

    # in the body the code is null (it fails its format) ...
    data = data_of({"price": {"currency": {"code": "https://evil.example", "amount": "5"}}}, ["price"])
    assert data == {"price": {"code": None, "amount": "5"}}
    assert templates.format_value(data["price"]) == "5"
    # ... and a value that did reach the text is still link-free in a copy
    entries = _entries(price={"code": "https://evil.example/x", "amount": "5"})
    _subject, copy = templates.render_respondent(entries, submitted_at="", language="en")
    assert "evil.example" not in copy


def test_control_characters_in_a_tag_never_break_a_line_of_the_team_mail():
    from backend.app.services.email_actions import templates

    entries = _entries(labels=["a\x00b‮dc", "x\r\nBcc: evil@example.test", "t​z"])
    block = templates.answers_block(entries, "en")
    rendered = templates.render(
        "Tags: {{labels}}\n\n{{answers}}", entries, form_title="t", submitted_at="", language="en", subject=False
    )
    for text in (block, rendered):
        assert "\x00" not in text and "‮" not in text and "​" not in text and "\r" not in text
        # the injected line is indented into its answer: no line of the mail starts with it
        assert not any(line.startswith("Bcc:") for line in text.split("\n"))
    subject = templates.render(
        "{{labels}}", entries, form_title="t", submitted_at="", language="en", subject=True
    )
    assert "\n" not in subject and "\r" not in subject
