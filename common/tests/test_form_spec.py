"""Form spec v1: committed schema, round trip, coverage of the stored model."""

import copy
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from common.form_spec import (
    FormSpec,
    SpecConversionError,
    form_to_spec,
    form_to_spec_dict,
    spec_to_form,
    spec_trust_settings,
    validation_errors,
)
from common.form_spec.roundtrip import (
    EXCLUDED_FIELD,
    EXCLUDED_FORM,
    EXCLUDED_PROPERTIES,
    creator_view,
)
from common.form_spec.models import (
    CURRENT_FIELD_TYPES,
    LEGACY_FIELD_TYPES,
    MAX_FIELDS,
    MAX_PAGES,
)
from common.form_spec.schema import SCHEMA_PATH, main, render_schema
from common.models.standard_form import (
    StandardFieldProperty,
    StandardFieldValidations,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
)
from tests.form_spec_fixture import RICH_TITLE, varied_form, varied_form_data


def test_the_committed_schema_is_up_to_date():
    assert SCHEMA_PATH.exists(), "run: uv run python -m common.form_spec.schema"
    assert SCHEMA_PATH.read_text() == render_schema(), (
        "docs/spec/form-spec-v1.schema.json is stale: "
        "run `uv run python -m common.form_spec.schema` from common/"
    )
    assert main(["--check"]) == 0


def test_the_schema_check_notices_a_stale_file(tmp_path, monkeypatch):
    stale = tmp_path / "schema.json"
    stale.write_text("{}\n")
    monkeypatch.setattr("common.form_spec.schema.SCHEMA_PATH", stale)
    assert main(["--check"]) == 1


def test_the_schema_is_versioned_and_closed():
    schema = json.loads(render_schema())
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert schema["properties"]["specVersion"]["const"] == "1"
    assert schema["required"] == ["specVersion"]
    assert schema["additionalProperties"] is False
    # camelCase names, server-owned data absent
    field = schema["$defs"]["FormField"]["properties"]
    assert {"colSpan", "whyWeAsk", "dateRules", "allowMultipleSelection"} <= set(field)
    current, legacy = field["type"]["anyOf"]
    assert "slide" not in current["enum"] + legacy["enum"]
    for absent in ("formId", "workspaceId", "publishedAt", "createdAt", "secrets"):
        assert absent not in schema["properties"]
    assert schema["$defs"]["Logo"]["properties"]["url"]["readOnly"] is True
    assert schema["properties"]["pages"]["maxItems"] == MAX_PAGES


def test_legacy_field_types_are_deprecated_but_still_read():
    schema = json.loads(render_schema())
    current, legacy = schema["$defs"]["FormField"]["properties"]["type"]["anyOf"]
    assert "deprecated" not in current and legacy["deprecated"] is True
    assert set(current["enum"]) == CURRENT_FIELD_TYPES
    assert set(legacy["enum"]) == LEGACY_FIELD_TYPES
    assert {"short_text", "group", "matrix", "IMAGE_CONTENT"} <= CURRENT_FIELD_TYPES
    assert {"h1", "input_short_text", "ranking", "payment"} <= LEGACY_FIELD_TYPES
    # every stored type except the page is one or the other
    assert CURRENT_FIELD_TYPES | LEGACY_FIELD_TYPES == {
        t.value for t in StandardFormFieldType
    } - {"slide"}
    document = {
        "specVersion": "1",
        "pages": [{"id": "p", "fields": [{"id": "h", "type": "h1", "title": "Hi"}]}],
    }
    form = spec_to_form(FormSpec.model_validate(document))
    assert form_to_spec(form).pages[0].fields[0].type == "h1"


def _document(pages: int, fields_per_page: int, children: int = 0) -> dict:
    def field(p, f):
        item = {"id": f"f{p}-{f}", "type": "short_text"}
        if children:
            item = {
                "id": f"g{p}-{f}",
                "type": "group",
                "fields": [
                    {"id": f"c{p}-{f}-{c}", "type": "short_text"}
                    for c in range(children)
                ],
            }
        return item

    return {
        "specVersion": "1",
        "pages": [
            {"id": f"p{p}", "fields": [field(p, f) for f in range(fields_per_page)]}
            for p in range(pages)
        ],
    }


def test_size_limits_of_a_document():
    FormSpec.model_validate(_document(MAX_PAGES, 10))  # 200 pages, 2000 fields
    with pytest.raises(ValidationError) as error:
        FormSpec.model_validate(_document(MAX_PAGES + 1, 1))
    assert validation_errors(error.value)[0]["path"] == "/pages"
    with pytest.raises(ValidationError) as error:
        FormSpec.model_validate(_document(10, 201))
    assert f"at most {MAX_FIELDS} fields" in str(error.value)
    # group questions count too: 10 pages x 10 groups x 20 questions + groups
    with pytest.raises(ValidationError):
        FormSpec.model_validate(_document(10, 10, children=20))


def test_round_trip_keeps_every_creator_controlled_value():
    form = varied_form()
    spec = form_to_spec(form)
    back = spec_to_form(spec)
    assert creator_view(back) == creator_view(form)
    # the spec of the copy is the same document
    assert form_to_spec(back) == spec
    # rich titles survive byte for byte, nulls included
    email = back.fields[0].properties.fields[1]
    assert email.title == RICH_TITLE
    # indexes come from the array order
    assert [p.index for p in back.fields] == [0, 1, 2]
    assert back.builder_version == "v2"
    # the comparison sees deep values (it is not vacuous)
    back.fields[1].properties.fields[3].properties.repeat.max_items = 5
    assert creator_view(back) != creator_view(form)


def test_round_trip_through_json():
    form = varied_form()
    document = json.loads(json.dumps(form_to_spec_dict(form)))
    assert document["specVersion"] == "1"
    back = spec_to_form(FormSpec.model_validate(document))
    assert creator_view(back) == creator_view(form)


def test_the_spec_document_shape():
    document = form_to_spec_dict(varied_form())
    assert list(document)[:2] == ["specVersion", "title"]
    page = document["pages"][0]
    assert page["sectionTitle"] == "About you"
    assert page["showQuestionNumbers"] is True
    assert page["jumps"][0]["target"] == "__SUBMIT__"
    name = page["fields"][0]
    assert name["validations"] == {
        "required": True,
        "minLength": 2,
        "maxLength": 80,
        "pattern": "^[^0-9]+$",
    }
    assert name["colSpan"] == 6
    assert document["trust"] == {
        "privacyPolicyUrl": "https://example.org/privacy",
        "retention": {"type": "days", "value": 30},
    }
    assert document["logo"]["url"].endswith("abc.png")
    assert document["endings"][0]["buttonLink"] == "https://example.org"
    # no server-owned or derived keys anywhere
    text = json.dumps(document)
    for key in ('"index"', '"formId"', '"builderVersion"', '"tag"'):
        assert key not in text


def test_trust_comes_from_the_association_settings_when_given():
    settings = SimpleNamespace(
        purpose="To plan the season.",
        retention_text="Deleted after the season.",
        privacy_policy_url="https://example.org/p",
        response_expiration_type="date",
        response_expiration="2031-01-01",
        require_verified_identity=True,
        allow_editing_response=False,
        show_submission_number=None,
    )
    spec = form_to_spec(varied_form(), settings)
    assert spec.trust.purpose == "To plan the season."
    assert spec.trust.retention.model_dump() == {"type": "date", "value": "2031-01-01"}
    assert spec_trust_settings(spec) == {
        "purpose": "To plan the season.",
        "retention_text": "Deleted after the season.",
        "privacy_policy_url": "https://example.org/p",
        "response_expiration_type": "date",
        "response_expiration": "2031-01-01",
        "require_verified_identity": True,
        "allow_editing_response": False,
    }


def test_a_form_without_pages_has_no_spec():
    flat = StandardForm(fields=[StandardFormField(id="q", type="short_text")])
    with pytest.raises(SpecConversionError) as error:
        form_to_spec(flat)
    assert error.value.errors[0]["path"] == "/fields/0"
    assert "not built from pages" in error.value.errors[0]["message"]


def test_unknown_and_missing_keys_are_reported_with_paths():
    document = form_to_spec_dict(varied_form())
    document["pages"][1]["fields"][0]["colour"] = "red"
    del document["pages"][0]["fields"][2]["type"]
    document["pages"][0]["fields"][0]["colSpan"] = 13
    with pytest.raises(ValidationError) as error:
        FormSpec.model_validate(document)
    found = {(e["path"], e["message"]) for e in validation_errors(error.value)}
    assert ("/pages/1/fields/0/colour", "Unknown property.") in found
    assert ("/pages/0/fields/2/type", "This property is required.") in found
    assert any(path == "/pages/0/fields/0/colSpan" for path, _ in found)


def test_model_rules_are_reported_in_spec_terms():
    document = form_to_spec_dict(varied_form())
    group = document["pages"][1]["fields"][3]
    group["fields"].append({"id": "nested", "type": "group", "fields": []})
    with pytest.raises(SpecConversionError) as error:
        spec_to_form(FormSpec.model_validate(document))
    assert error.value.errors[0]["path"] == "/pages/1/fields/3"
    assert "cannot contain another group" in error.value.errors[0]["message"]


def test_every_stored_property_is_covered_or_excluded_on_purpose():
    """A new property of the stored model must be added to the spec (and
    the adapters) or excluded here, deliberately."""
    covered_form = {
        "title",
        "description",
        "logo",
        "logo_position",
        "logo_alt",
        "use_workspace_logo",
        "fields",
        "hidden_fields",
        "settings",
        "theme",
        "welcome_page",
        "thankyou_page",
    }
    assert set(StandardForm.model_fields) == covered_form | EXCLUDED_FORM
    covered_field = {
        "id",
        "title",
        "description",
        "value",
        "type",
        "properties",
        "validations",
        "attachment",
        "image_url",
        "internal",
    }
    assert set(StandardFormField.model_fields) == covered_field | EXCLUDED_FIELD
    covered_properties = {
        "logic",
        "jumps",
        "position",
        "choices",
        "fields",
        "allow_multiple_selection",
        "allow_other_choice",
        "hide_marks",
        "placeholder",
        "steps",
        "start_from",
        "rating_shape",
        "labels",
        "date_format",
        "theme",
        "layout",
        "row_titles",
        "column_titles",
        "tabular_value",
        "col_span",
        "repeat",
        "label",
        "date_rules",
        "why_we_ask",
        "section_title",
        "show_question_numbers",
    }
    assert (
        set(StandardFieldProperty.model_fields)
        == covered_properties | EXCLUDED_PROPERTIES
    )
    assert set(StandardFieldValidations.model_fields) == {
        "required",
        "max_length",
        "min_length",
        "min_value",
        "max_value",
        "regex",
        "min_choices",
        "max_choices",
    }


def test_show_question_numbers_is_kept_by_the_stored_model():
    page = StandardFormField.model_validate(
        {"id": "p", "type": "slide", "properties": {"showQuestionNumbers": True}}
    )
    assert page.properties.show_question_numbers is True


def test_spec_to_form_does_not_share_state_with_the_spec():
    spec = form_to_spec(varied_form())
    before = copy.deepcopy(spec)
    form = spec_to_form(spec)
    form.fields[0].properties.fields[0].title = "changed"
    assert spec == before


def test_the_readme_example_is_a_valid_document():
    readme = (SCHEMA_PATH.parent / "README.md").read_text()
    example = readme.split("```json", 1)[1].split("```", 1)[0]
    spec = FormSpec.model_validate(json.loads(example))
    form = spec_to_form(spec)
    assert form.fields[0].properties.fields[2].properties.logic.action == "SHOW"
    assert form.settings.response_expiration == "30"


def test_varied_fixture_is_valid_input():
    # guards the fixture itself: it must stay a valid stored form
    assert (
        StandardForm(**varied_form_data())
        .fields[1]
        .properties.fields[3]
        .properties.repeat
    )
