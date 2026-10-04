"""Internal fields and repeating groups: not allowed together (v1), and the
internal-field strip/drop helpers cover group children anyway."""

import json

import pytest
from common.models.standard_form import StandardForm, StandardFormField
from pydantic import ValidationError

from tests.app.auth_helpers import access_token
from backend.app.container import container
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.internal_fields import (
    drop_respondent_internal_answers,
    internal_field_ids,
    strip_internal_fields,
)
from tests.app.controllers.data import testUser

pytestmark = pytest.mark.asyncio


def _group(internal_child=False, group_internal=False):
    child = {"id": "ref", "type": "short_text", "title": "Reference"}
    if internal_child:
        child["internal"] = True
    group = {
        "id": "g",
        "type": "group",
        "title": "Applicants",
        "properties": {
            "repeat": {"minItems": 1, "maxItems": 3, "itemLabel": "Applicant"},
            "fields": [{"id": "name", "type": "short_text", "title": "Name"}, child],
        },
    }
    if group_internal:
        group["internal"] = True
    return group


def _form(group):
    return {
        "title": "Applicants",
        "builder_version": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {"fields": [group]},
            }
        ],
    }


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def test_model_rejects_internal_children_and_internal_groups():
    with pytest.raises(ValidationError, match="Internal fields cannot be placed"):
        StandardFormField(**_group(internal_child=True))
    with pytest.raises(ValidationError, match="cannot be an internal field"):
        StandardFormField(**_group(group_internal=True))
    assert StandardFormField(**_group()).properties.repeat is not None


async def test_builder_save_with_an_internal_group_child_is_422(client, workspace):
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**_form(_group())), testUser
    )
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}",
        data={"form_body": json.dumps(_form(_group(internal_child=True)))},
        cookies=_cookies(testUser),
    )
    assert response.status_code == 422
    assert "Internal fields cannot be placed" in response.text


def _ai_form():
    page = {
        "id": "page-1",
        "index": 0,
        "type": "slide",
        "properties": {
            "fields": [
                {
                    "id": "staff",
                    "index": 0,
                    "type": "short_text",
                    "title": "Staff note",
                    "internal": True,
                },
                {**_group(), "index": 1},
            ]
        },
    }
    return StandardForm(builder_version="v2", title="t", fields=[page])


def test_ai_ops_refuse_internal_fields_in_groups():
    _, results = apply_form_ops(
        _ai_form(),
        parse_ops(
            [
                {
                    "op": "add_field",
                    "groupId": "g",
                    "field": {"title": "Ref", "type": "short_text", "internal": True},
                },
                {"op": "move_field", "fieldId": "staff", "toGroupId": "g", "index": 0},
                {"op": "update_field", "fieldId": "name", "patch": {"internal": True}},
                {"op": "update_field", "fieldId": "g", "patch": {"internal": True}},
                {
                    "op": "add_group",
                    "pageId": "page-1",
                    "title": "More",
                    "fields": [
                        {"title": "Ref", "type": "short_text", "internal": True}
                    ],
                },
            ]
        ),
    )
    assert [r.ok for r in results] == [False] * 5, [r.message for r in results]
    assert "Internal fields cannot be placed" in results[0].message


def _hand_built_form():
    """A form that bypasses validation (e.g. written straight to the store)."""
    return _form(_group(internal_child=True))


def test_strip_covers_internal_group_children():
    form = _hand_built_form()
    assert internal_field_ids(form) == {"ref"}
    stripped = strip_internal_fields(form)
    group = stripped["fields"][0]["properties"]["fields"][0]
    assert [c["id"] for c in group["properties"]["fields"]] == ["name"]


def test_drop_covers_internal_answers_inside_items():
    response = {
        "answers": {
            "ref": {"type": "text", "text": "top level"},
            "g": {
                "type": "group",
                "items": [
                    {
                        "name": {"type": "text", "text": "A"},
                        "ref": {"type": "text", "text": "x"},
                    },
                    {"ref": {"type": "text", "text": "y"}},
                ],
            },
        }
    }
    dropped = drop_respondent_internal_answers(
        response, internal_field_ids(_hand_built_form())
    )
    assert dropped == 3
    assert "ref" not in response["answers"]
    assert response["answers"]["g"]["items"] == [
        {"name": {"type": "text", "text": "A"}},
        {},
    ]
