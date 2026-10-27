"""Our Generic JSON body against bodies a real Open Formulieren 4.0.6 sent
(tests/fixtures/registration, see its README): same keys, same values, same
schema fragments, and every deliberate difference spelled out here."""

import datetime as dt
import json
from pathlib import Path

from common.models.standard_form import StandardForm

from backend.app.services.registration import body

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "registration"
# the moment the real body was captured (its registration_timestamp)
NOW = dt.datetime(2026, 10, 26, 23, 59, 0, tzinfo=dt.timezone.utc)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def choice(*ids):
    return [{"id": i, "value": i} for i in ids]


# the questions of the form the fixtures were captured from, as our fields
FORM = StandardForm(
    builder_version="v2",
    title="capture",
    fields=[
        {
            "id": "s1",
            "type": "slide",
            "properties": {
                "fields": [
                    {
                        "id": "firstName",
                        "type": "short_text",
                        "title": "First name",
                        "validations": {"max_length": 50},
                    },
                    {"id": "remarks", "type": "long_text", "title": "Remarks"},
                    {"id": "email", "type": "email", "title": "Email address"},
                    {"id": "age", "type": "number", "title": "Age"},
                    {"id": "birthDate", "type": "date", "title": "Date of birth"},
                    {
                        "id": "contactPreference",
                        "type": "multiple_choice",
                        "title": "How should we contact you?",
                        "properties": {"choices": choice("email", "phone")},
                    },
                    {
                        "id": "topics",
                        "type": "multiple_choice",
                        "title": "Topics",
                        "properties": {
                            "allow_multiple_selection": True,
                            "choices": choice("news", "events", "offers"),
                        },
                    },
                    {"id": "consent", "type": "yes_no", "title": "I agree"},
                    {"id": "attachment", "type": "file_upload", "title": "Attachment"},
                    {
                        "id": "children",
                        "type": "group",
                        "title": "Children",
                        "properties": {
                            "repeat": {
                                "minItems": 0,
                                "maxItems": 5,
                                "itemLabel": "Child",
                            },
                            "fields": [
                                {
                                    "id": "childName",
                                    "type": "short_text",
                                    "title": "Child name",
                                    "validations": {"max_length": 1000},
                                },
                                {
                                    "id": "childAge",
                                    "type": "number",
                                    "title": "Child age",
                                },
                            ],
                        },
                    },
                ]
            },
        }
    ],
)
KEYS = [
    "firstName",
    "remarks",
    "email",
    "age",
    "birthDate",
    "contactPreference",
    "topics",
    "consent",
    "attachment",
    "children",
]

FULL = {
    "firstName": {"type": "text", "text": "Ada"},
    "remarks": {"type": "text", "text": "A synthetic remark."},
    "email": {"type": "email", "email": "ada@example.test"},
    "age": {"type": "number", "number": 36},
    "birthDate": {"type": "date", "date": "1990-01-02"},
    "contactPreference": {"type": "choice", "choice": {"value": "phone"}},
    "topics": {"type": "choices", "choices": {"values": ["news", "offers"]}},
    "consent": {"type": "boolean", "boolean": True},
    "attachment": {
        "type": "file",
        "file_metadata": {"id": "f1", "name": "note-one.txt"},
    },
    "children": {
        "type": "group",
        "items": [
            {
                "childName": {"type": "text", "text": "Bo"},
                "childAge": {"type": "number", "number": 3},
            },
            {
                "childName": {"type": "text", "text": "Cy"},
                "childAge": {"type": "number", "number": 5},
            },
        ],
    },
}
FIRST_ONLY = {"firstName": {"type": "text", "text": "Bea"}}


def ours(answers, as_list=("topics",), keys=KEYS):
    index = body.variables_of(FORM)
    values, schema = body.build_values(
        index,
        [(k, k) for k in keys],
        answers,
        None,
        as_list,
        lambda _id: b"synthetic file one\n",
    )
    metadata, metadata_schema = body.build_metadata(
        body.FIXED_METADATA, public_reference="OF-D3L3H5", form_version="", now=NOW
    )
    return json.loads(body.serialize(values, schema, metadata, metadata_schema))


def compare(theirs: dict, mine: dict, keys=KEYS, differences=()):
    assert list(mine) == ["values", "values_schema", "metadata", "metadata_schema"]
    assert list(mine) == list(theirs)  # the four keys, in their order
    assert mine["values_schema"]["$schema"] == theirs["values_schema"]["$schema"]
    assert mine["values_schema"]["required"] == [
        k for k in theirs["values_schema"]["required"] if k in keys
    ]
    assert mine["values_schema"]["additionalProperties"] is False
    for key in keys:
        if key in differences:
            continue
        assert mine["values"][key] == theirs["values"][key], key
        assert (
            mine["values_schema"]["properties"][key]
            == theirs["values_schema"]["properties"][key]
        ), key


def test_every_question_answered_matches_the_real_body():
    theirs = load("generic_json_full.json")
    mine = ours(FULL)
    # the multiple-file question has no counterpart here (a file question holds one file)
    compare(theirs, mine, differences=())
    assert mine["metadata"] == theirs["metadata"]
    assert mine["metadata_schema"] == theirs["metadata_schema"]
    assert mine["values"] == {k: v for k, v in theirs["values"].items() if k in KEYS}


def test_unanswered_questions_follow_the_real_body_where_it_is_exact():
    theirs = load("generic_json_unanswered.json")
    mine = ours(FIRST_ONLY)
    # text-like "" and the empty list / group / file match as sent by the real thing
    for key in (
        "firstName",
        "remarks",
        "email",
        "contactPreference",
        "topics",
        "children",
        "attachment",
        "consent",
    ):
        if key == "consent":
            continue
        assert mine["values"][key] == theirs["values"][key], key
        assert (
            mine["values_schema"]["properties"][key]
            == theirs["values_schema"]["properties"][key]
        ), key
    # deliberate differences:
    # - an unanswered yes/no is null (they send false) and says so in its schema
    assert mine["values"]["consent"] is None and theirs["values"]["consent"] is False
    assert mine["values_schema"]["properties"]["consent"]["type"] == ["boolean", "null"]
    # - an unanswered number or date is null in both; our schema admits it
    assert mine["values"]["age"] is None and theirs["values"]["age"] is None
    assert mine["values_schema"]["properties"]["age"]["type"] == ["number", "null"]
    assert theirs["values_schema"]["properties"]["age"]["type"] == "number"
    assert mine["values"]["birthDate"] is None and theirs["values"]["birthDate"] is None
    assert mine["values_schema"]["properties"]["birthDate"]["type"] == [
        "string",
        "null",
    ]


def test_a_selectboxes_question_not_turned_into_a_list_is_an_object():
    theirs = load("generic_json_selectboxes_as_object.json")
    mine = ours(FIRST_ONLY, as_list=())
    assert (
        mine["values"]["topics"]
        == theirs["values"]["topics"]
        == {"news": False, "events": False, "offers": False}
    )
    assert (
        mine["values_schema"]["properties"]["topics"]
        == theirs["values_schema"]["properties"]["topics"]
    )


def test_selected_options_in_the_object_form():
    mine = ours(FULL, as_list=())
    assert mine["values"]["topics"] == {"news": True, "events": False, "offers": True}


def test_the_real_metadata_names_and_our_fixed_metadata_agree():
    theirs = load("generic_json_full.json")
    assert list(theirs["metadata"]) == list(body.FIXED_METADATA)
    assert list(theirs["metadata_schema"]["properties"]) == list(body.FIXED_METADATA)
    # their timestamp: whole seconds, UTC, "Z"
    assert theirs["metadata"]["registration_timestamp"].endswith("Z")
    assert ours(FULL)["metadata"]["registration_timestamp"] == "2026-10-26T23:59:00Z"


def test_the_body_is_valid_json_in_utf8_without_the_answers_in_the_schema():
    mine = ours(FULL)
    schema_text = json.dumps(mine["values_schema"])
    for answer in ("Ada", "ada@example.test", "A synthetic remark."):
        assert answer not in schema_text
