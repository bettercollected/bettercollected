"""A question's answer rules (``validations`` beyond Required) are kept.

The builder's "Answer rules" panel writes min/max length, a format pattern,
min/max value (with "whole numbers only" as a pattern) and min/max choices
into a field's validations. They must survive a save, go live with a
publish and come back to the respondent page, which enforces them."""

import json

from httpx import AsyncClient

from backend.app.container import container
from tests.app.controllers.data import testUser

POSTCODE = "^[1-9][0-9]{3} ?[A-Za-z]{2}$"
WHOLE_NUMBERS = "^-?\\d+$"


def _forms_url(workspace, form_id=""):
    base = f"/api/v1/workspaces/{workspace.id}/forms"
    return f"{base}/{form_id}" if form_id else base


def _body():
    return {
        "title": "Answer rules",
        "builderVersion": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "layout": "SINGLE_COLUMN_NO_BACKGROUND",
                    "fields": [
                        {
                            "id": "postcode",
                            "index": 0,
                            "type": "short_text",
                            "title": "Postcode",
                            "validations": {
                                "required": True,
                                "minLength": 6,
                                "maxLength": 7,
                                "regex": POSTCODE,
                            },
                        },
                        {
                            "id": "people",
                            "index": 1,
                            "type": "number",
                            "title": "How many people?",
                            "validations": {
                                "minValue": 0,
                                "maxValue": 12.5,
                                "regex": WHOLE_NUMBERS,
                            },
                        },
                        {
                            "id": "topics",
                            "index": 2,
                            "type": "multiple_choice",
                            "title": "Topics",
                            "properties": {
                                "allowMultipleSelection": True,
                                "choices": [
                                    {"id": "c1", "value": "One"},
                                    {"id": "c2", "value": "Two"},
                                    {"id": "c3", "value": "Three"},
                                ],
                            },
                            "validations": {"minChoices": 1, "maxChoices": 2},
                        },
                    ],
                },
            }
        ],
        "thankyouPage": [{"layout": "SINGLE_COLUMN_NO_BACKGROUND"}],
    }


def _rules(form_json):
    fields = form_json["fields"][0]["properties"]["fields"]
    return {
        f["id"]: {k: v for k, v in (f.get("validations") or {}).items() if v is not None}
        for f in fields
    }


EXPECTED = {
    "postcode": {"required": True, "minLength": 6, "maxLength": 7, "regex": POSTCODE},
    "people": {"minValue": 0, "maxValue": 12.5, "regex": WHOLE_NUMBERS},
    "topics": {"minChoices": 1, "maxChoices": 2},
}


async def test_answer_rules_are_saved_published_and_served(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    reply = await client.patch(
        _forms_url(workspace, form_id),
        data={"form_body": json.dumps(_body())},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert _rules(reply.json()) == EXPECTED

    stored = await container.form_repo().get_form_document_by_id(form_id)
    postcode = stored.fields[0].properties.fields[0].validations
    assert (postcode.min_length, postcode.max_length, postcode.regex) == (
        6,
        7,
        POSTCODE,
    )
    assert stored.fields[0].properties.fields[1].validations.min_value == 0

    await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    live = await client.get(_forms_url(workspace, form_id), params={"published": True})
    assert live.status_code == 200, live.text
    assert _rules(live.json()) == EXPECTED


async def test_clearing_a_rule_removes_it(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    body = _body()
    await client.patch(
        _forms_url(workspace, form_id),
        data={"form_body": json.dumps(body)},
        cookies=test_user_cookies,
    )
    # The builder drops a cleared rule from the field's validations.
    body["fields"][0]["properties"]["fields"][0]["validations"] = {"required": True}
    reply = await client.patch(
        _forms_url(workspace, form_id),
        data={"form_body": json.dumps(body)},
        cookies=test_user_cookies,
    )
    assert reply.status_code == 200, reply.text
    assert _rules(reply.json())["postcode"] == {"required": True}
