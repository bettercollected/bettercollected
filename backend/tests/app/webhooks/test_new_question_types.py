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
    assert props["price"]["properties"]["code"]["enum"] == ["USD", "EUR"]
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
