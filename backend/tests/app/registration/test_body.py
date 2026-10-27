"""Body building details: which variables exist, what is left out, limits."""

import base64
import json

import pytest
from common.models.standard_form import StandardForm

from backend.app.services.registration import body
from tests.app.registration.helpers import FIELDS


def form_with(fields, hidden=None):
    return StandardForm(
        builder_version="v2",
        title="t",
        hidden_fields=hidden,
        fields=[{"id": "s1", "type": "slide", "properties": {"fields": fields}}],
    )


def build(form, mapping, answers, hidden=None, read=lambda _id: b"", as_list=()):
    return body.build_values(
        body.variables_of(form),
        [(s, s) for s in mapping],
        answers,
        hidden,
        as_list,
        read,
    )


def test_content_blocks_internal_fields_and_group_items_are_not_mappable():
    form = form_with(
        [
            *FIELDS,
            {"id": "staff", "type": "short_text", "title": "Staff", "internal": True},
        ],
        hidden=["utm_source"],
    )
    sources = {v.source for v in body.mappable(form)}
    assert {"name", "people", "upload", "utm_source"} <= sources
    assert (
        "intro" not in sources
        and "staff" not in sources
        and "people.pname" not in sources
    )
    index = body.variables_of(form)
    assert "staff" not in index
    assert (
        index["people.pname"].kind == "group_child" and index["people.pname"].supported
    )


def test_a_hidden_field_is_its_captured_text_or_empty():
    form = form_with(
        [{"id": "name", "type": "short_text", "title": "Name"}], hidden=["utm_source"]
    )
    values, schema = build(form, ["utm_source"], {}, {"utm_source": "newsletter"})
    assert (
        values == {"utm_source": "newsletter"}
        and schema["properties"]["utm_source"]["type"] == "string"
    )
    assert build(form, ["utm_source"], {}, None)[0] == {"utm_source": ""}


def test_a_source_the_form_no_longer_has_is_left_out():
    form = form_with([{"id": "name", "type": "short_text", "title": "Name"}])
    values, schema = build(
        form, ["name", "removed"], {"name": {"type": "text", "text": "A"}}
    )
    assert list(values) == ["name"] and schema["required"] == ["name"]


def test_other_text_is_kept_as_written_next_to_the_options():
    form = form_with(
        [
            {
                "id": "c",
                "type": "multiple_choice",
                "title": "C",
                "properties": {
                    "allow_other_choice": True,
                    "choices": [{"id": "a", "value": "Alpha"}],
                },
            }
        ]
    )
    other = build(
        form, ["c"], {"c": {"type": "choice", "choice": {"other": "Something else"}}}
    )[0]["c"]
    assert other == "Something else"
    assert (
        build(form, ["c"], {"c": {"type": "choice", "choice": {"value": "a"}}})[0]["c"]
        == "Alpha"
    )


def test_an_option_without_a_text_is_item_n_like_the_form_shows_it():
    form = form_with(
        [
            {
                "id": "c",
                "type": "dropdown",
                "title": "C",
                "properties": {"choices": [{"id": "a"}, {"id": "b", "label": "Bee"}]},
            }
        ]
    )
    assert (
        build(form, ["c"], {"c": {"type": "choice", "choice": {"value": "a"}}})[0]["c"]
        == "Item 1"
    )
    assert (
        build(form, ["c"], {"c": {"type": "choice", "choice": {"value": "b"}}})[0]["c"]
        == "Bee"
    )


def test_a_calculated_value_is_sent_as_stored():
    form = form_with(
        [
            {
                "id": "total",
                "type": "calculated",
                "title": "Total",
                "properties": {"expression": {"var": "x"}},
            }
        ]
    )
    values, schema = build(
        form, ["total"], {"total": {"type": "number", "number": 12.5}}
    )
    assert (
        values == {"total": 12.5} and schema["properties"]["total"]["type"] == "number"
    )


def test_files_are_base64_and_capped():
    form = form_with([{"id": "up", "type": "file_upload", "title": "Up"}])
    answer = {"up": {"type": "file", "fileMetadata": {"id": "f", "name": "a.txt"}}}
    values, _ = build(form, ["up"], answer, read=lambda _id: b"abc")
    assert values["up"] == {
        "file_name": "a.txt",
        "content": base64.b64encode(b"abc").decode(),
    }
    with pytest.raises(body.FileTooLarge):
        build(form, ["up"], answer, read=lambda _id: b"x" * (body.MAX_FILE_BYTES + 1))
    assert build(form, ["up"], {}, read=lambda _id: b"")[0] == {"up": None}


def test_group_items_with_missing_children_keep_their_shape():
    form = form_with([FIELDS[9]])
    answer = {
        "people": {
            "type": "group",
            "items": [{"pname": {"type": "text", "text": "Bo"}}],
        }
    }
    values, schema = build(form, ["people"], answer)
    assert values["people"] == [{"pname": "Bo", "pyears": None}]
    items = schema["properties"]["people"]["items"]
    assert items["required"] == ["pname", "pyears"] and items["properties"]["pyears"][
        "type"
    ] == ["number", "null"]
    assert schema["properties"]["people"]["maxItems"] == 5


def test_the_body_is_utf8_json_with_the_four_keys_in_order():
    values, schema = body.build_values({}, [], {}, None, [], lambda _id: b"")
    metadata, metadata_schema = values, schema
    payload = body.serialize({"naïve": "é"}, schema, metadata, metadata_schema)
    assert list(json.loads(payload)) == [
        "values",
        "values_schema",
        "metadata",
        "metadata_schema",
    ]
    assert "é".encode() in payload
