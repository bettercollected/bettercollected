"""Field rules through the HTTP routes: the builder save lists the rules it
dropped (``droppedFieldRules``), and a template body far over the rule cap
is refused before it is parsed (services/field_rules.py)."""

import json
import time

from httpx import AsyncClient

from backend.app.container import container

API = "/api/v1"


def _rule(rule_id, field_id):
    return {
        "id": rule_id,
        "when": {
            "conditions": [
                {"fieldId": field_id, "comparison": "IS_EQUAL", "value": "x"}
            ]
        },
        "then": {"required": True},
    }


def _body(fields):
    return {
        "title": "Rules",
        "builderVersion": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {"fields": fields},
            }
        ],
    }


def _q(field_id, rules=None):
    field = {"id": field_id, "type": "short_text", "title": field_id}
    if rules:
        field["properties"] = {"rules": rules}
    return field


async def test_the_builder_save_lists_the_rules_it_dropped(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    url = f"{API}/workspaces/{workspace.id}/forms/{workspace_form.form_id}"
    # a rule reading a question the form does not have: dropped, not refused
    response = await client.patch(
        url,
        cookies=test_user_cookies,
        data={
            "form_body": json.dumps(_body([_q("a"), _q("b", [_rule("r1", "gone")])]))
        },
    )
    assert response.status_code == 200, response.text
    dropped = response.json()["droppedFieldRules"]
    assert [(d["fieldId"], d["ruleId"]) for d in dropped] == [("b", "r1")]
    assert "gone" in dropped[0]["message"]
    stored = await container.form_service().get_form_document_by_id(
        workspace_form.form_id
    )
    assert stored.fields[0].properties.fields[1].properties.rules is None
    # a save with nothing dropped carries no list
    response = await client.patch(
        url, cookies=test_user_cookies, data={"form_body": json.dumps(_body([_q("a")]))}
    )
    assert response.status_code == 200, response.text
    assert response.json().get("droppedFieldRules") is None


async def test_a_template_far_over_the_rule_cap_is_refused_before_parsing(
    client: AsyncClient, workspace, test_user_cookies
):
    huge = {"var": "y"}  # form fields are capped at 1 MB: many small rules
    fields = [
        _q(
            f"m{i}",
            [
                {
                    "id": f"m{i}-{j}",
                    "when": {"expression": huge},
                    "then": {"required": True},
                }
                for j in range(8)
            ],
        )
        for i in range(200)
    ]
    template = {"title": "T", "fields": _body(fields)["fields"]}
    start = time.perf_counter()
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/template",
        cookies=test_user_cookies,
        data={"template_body": json.dumps(template)},
    )
    assert time.perf_counter() - start < 2.0
    assert response.status_code == 422, response.text
    assert "at most 100 rules" in response.text
