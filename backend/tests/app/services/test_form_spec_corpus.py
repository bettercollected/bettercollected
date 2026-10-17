"""The spec round trip on the forms the backend already has as fixtures:
the seeded flow templates, the controller test form and a form built by
every creating op. Each keeps everything the spec covers
(common/form_spec/roundtrip.py) and comes back as the same document."""

import copy
import json

import pytest
from common.form_spec import FormSpec, form_to_spec, form_to_spec_dict, spec_to_form
from common.form_spec.roundtrip import creator_view
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
)

from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.form_spec.checks import check_spec_document
from scripts.seed_flow_templates import TEMPLATE_BUILDERS
from tests.app.controllers.data import formData_test


def _templates():
    for build in TEMPLATE_BUILDERS:
        template = build()
        yield build.__name__, StandardForm(
            title=template["title"],
            description=template["description"],
            fields=template["fields"],
            builder_version="v2",
        )


def _built_by_ops():
    blank = StandardForm(
        builder_version="v2",
        title="Built",
        fields=[
            StandardFormField(
                id="p",
                type=StandardFormFieldType.SLIDE,
                properties=StandardFieldProperty(fields=[]),
            )
        ],
    )
    form, results = apply_form_ops(
        blank,
        parse_ops(
            [
                {
                    "op": "add_page",
                    "ref": "two",
                    "fields": [{"title": "Dog?", "type": "yes_no", "ref": "dog"}],
                },
                {
                    "op": "add_field",
                    "pageId": "p",
                    "field": {
                        "title": "Email",
                        "type": "email",
                        "whyWeAsk": "Receipt",
                        "colSpan": 6,
                    },
                },
                {
                    "op": "add_field",
                    "pageId": "p",
                    "field": {
                        "title": "Size",
                        "type": "dropdown",
                        "choices": ["S", "M"],
                    },
                },
                {
                    "op": "add_field",
                    "pageId": "p",
                    "field": {"title": "Score", "type": "rating", "steps": 5},
                },
                {
                    "op": "add_field",
                    "pageId": "p",
                    "field": {"title": "Start", "type": "date", "label": "From"},
                },
                {
                    "op": "add_group",
                    "pageId": "$ref:two",
                    "title": "People",
                    "itemLabel": "Person",
                    "fields": [{"title": "Name", "type": "short_text"}],
                },
                {
                    "op": "set_page_jumps",
                    "pageId": "p",
                    "jumps": [
                        {
                            "conditions": [
                                {"fieldId": "$ref:dog", "comparison": "IS_EMPTY"}
                            ],
                            "target": "__SUBMIT__",
                        }
                    ],
                },
                {"op": "duplicate_page", "pageId": "$ref:two"},
                {"op": "set_section_title", "pageIndex": 0, "title": "Start"},
                {"op": "set_question_numbering", "show": True},
                {
                    "op": "set_field_validation",
                    "fieldId": "$ref:dog",
                    "validation": {"required": True},
                },
            ]
        ),
    )
    assert all(r.ok for r in results), results
    return form


CORPUS = list(_templates()) + [
    ("controller test form", StandardForm(**copy.deepcopy(formData_test))),
    ("built by ops", _built_by_ops()),
]


@pytest.mark.parametrize("name, form", CORPUS, ids=[name for name, _ in CORPUS])
def test_round_trip(name, form):
    spec = form_to_spec(form)
    back = spec_to_form(spec)
    assert creator_view(back) == creator_view(form)
    assert form_to_spec(back) == spec
    # and through JSON, as a client would send it back
    again = spec_to_form(FormSpec.model_validate(form_to_spec_dict(form)))
    assert creator_view(again) == creator_view(form)


@pytest.mark.parametrize(
    "name, form",
    [c for c in CORPUS if c[0] != "controller test form"],
    ids=[name for name, _ in CORPUS if name != "controller test form"],
)
def test_the_spec_of_a_real_form_validates(name, form):
    result = check_spec_document(form_to_spec_dict(form))
    assert result["valid"], result["errors"]


def test_the_committed_json_schema_accepts_the_corpus_and_refuses_typos():
    """The published schema agrees with the models: a JSON Schema
    validator (not pydantic) accepts every document of the corpus."""
    jsonschema = pytest.importorskip("jsonschema")
    from common.form_spec.schema import SCHEMA_PATH

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    for name, form in CORPUS:
        document = form_to_spec_dict(form)
        errors = list(validator.iter_errors(document))
        assert errors == [], (name, [e.message for e in errors])
    document = form_to_spec_dict(CORPUS[0][1])
    document["pages"][0]["fields"][0]["colour"] = "red"
    assert not validator.is_valid(document)
    del document["pages"][0]["fields"][0]["colour"]
    document["specVersion"] = "2"
    assert not validator.is_valid(document)
