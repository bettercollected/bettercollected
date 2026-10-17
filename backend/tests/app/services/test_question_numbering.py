"""A page's "number the questions" switch survives a builder save and is
served back (it used to be dropped by the stored model)."""

import json

from common.models.standard_form import StandardForm

from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.models.dtos.response_dtos import StandardFormCamelModel


def _body(show):
    return {
        "title": "Form",
        "fields": [
            {
                "id": "page-1",
                "type": "slide",
                "properties": {"showQuestionNumbers": show, "fields": []},
            }
        ],
    }


def test_the_builder_save_keeps_show_question_numbers():
    form = _parse_form_body(json.dumps(_body(True)))
    assert form.fields[0].properties.show_question_numbers is True
    served = StandardFormCamelModel(**form.model_dump()).model_dump(
        by_alias=True, exclude_none=True
    )
    assert served["fields"][0]["properties"]["showQuestionNumbers"] is True


def test_turning_it_off_is_kept_too():
    form = _parse_form_body(json.dumps(_body(False)))
    assert form.fields[0].properties.show_question_numbers is False
    assert (
        StandardForm(**form.model_dump()).fields[0].properties.show_question_numbers
        is False
    )
