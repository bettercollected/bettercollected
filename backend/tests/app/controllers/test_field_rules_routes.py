"""Field rules through the HTTP routes: the builder save lists the rules it
dropped (``droppedFieldRules``), and a template body far over the rule cap
is refused before it is parsed (services/field_rules.py)."""

import json
import time

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.config import settings
from tests.app.controllers.test_mcp_server import (
    _call_tool,
    _make_key,
    _make_v2,
    _tool_text,
)
from tests.app.controllers.test_public_api import (
    BASE as PUBLIC,
    SPEC,
    _auth,
    _create,
    _is_error,
    _token,
)

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
    # the template router's own count, before any model is built (not the
    # save check's later "A form can have at most ..." refusal)
    assert "A template can have at most 100 rules; this one has 1600." in response.text


async def test_the_builder_save_after_a_question_became_internal_is_not_refused(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    url = f"{API}/workspaces/{workspace.id}/forms/{workspace_form.form_id}"
    ruled = _body([_q("a"), _q("b", [_rule("r1", "a")])])
    response = await client.patch(
        url, cookies=test_user_cookies, data={"form_body": json.dumps(ruled)}
    )
    assert response.status_code == 200, response.text
    # the builder marks "b" internal; its rules stay in the body it autosaves
    ruled["fields"][0]["properties"]["fields"][1]["internal"] = True
    for _ in range(2):
        response = await client.patch(
            url, cookies=test_user_cookies, data={"form_body": json.dumps(ruled)}
        )
        assert response.status_code == 200, response.text
        dropped = response.json()["droppedFieldRules"]
        assert [(d["fieldId"], d["ruleId"]) for d in dropped] == [("b", "r1")]
    stored = await container.form_service().get_form_document_by_id(
        workspace_form.form_id
    )
    assert stored.fields[0].properties.fields[1].properties.rules is None


# --- the operation through the public API and MCP ---------------------------------


SET_RULES = [
    {
        "op": "set_field_rules",
        "fieldId": "name",
        "rules": [
            {
                "id": "r1",
                "when": {
                    "conditions": [
                        {"fieldId": "dinner", "comparison": "IS_EQUAL", "value": "Yes"}
                    ]
                },
                "then": {"required": True},
            }
        ],
    }
]


async def test_the_public_api_ops_follow_the_flag(
    client: AsyncClient, workspace, monkeypatch
):
    token = await _token(workspace.id)
    form_id = (await _create(client, token, SPEC)).json()["formId"]
    url = f"{PUBLIC}/forms/{form_id}/ops"
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", False)
    body = _is_error(
        await client.post(url, json={"ops": SET_RULES}, headers=_auth(token)),
        422,
        "ops_failed",
    )
    assert "FIELD_RULES_ENABLED" in body["errors"][0]["message"]
    stored = await container.form_repo().get_form_document_by_id(form_id)
    assert stored.fields[0].properties.fields[0].properties.rules is None
    # a dry run says the same and stores nothing
    dry = await client.post(
        f"{url}/dry-run", json={"ops": SET_RULES, "atomic": False}, headers=_auth(token)
    )
    assert dry.status_code == 200 and dry.json()["results"][0]["ok"] is False

    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    response = await client.post(url, json={"ops": SET_RULES}, headers=_auth(token))
    assert response.status_code == 200, response.text
    fetched = await client.get(f"{PUBLIC}/forms/{form_id}", headers=_auth(token))
    rules = fetched.json()["pages"][0]["fields"][0]["rules"]
    assert rules[0]["id"] == "r1" and rules[0]["then"] == {"required": True}


async def test_a_broken_rule_is_a_failed_op_not_a_stored_rule(
    client: AsyncClient, workspace, monkeypatch
):
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    token = await _token(workspace.id)
    form_id = (await _create(client, token, SPEC)).json()["formId"]
    broken = [
        {
            **SET_RULES[0],
            "rules": [
                {
                    "id": "r1",
                    "when": {"expression": {"+": [{"var": "nobody"}, 1]}},
                    "then": {"required": True},
                }
            ],
        }
    ]
    body = _is_error(
        await client.post(
            f"{PUBLIC}/forms/{form_id}/ops", json={"ops": broken}, headers=_auth(token)
        ),
        422,
        "ops_failed",
    )
    assert "nobody" in body["errors"][0]["message"]
    stored = await container.form_repo().get_form_document_by_id(form_id)
    assert stored.fields[0].properties.fields[0].properties.rules is None


async def test_the_validate_endpoint_warns_while_the_flag_is_off(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    name, dinner = SPEC["pages"][0]["fields"]
    rule = {
        "id": "r1",
        "when": {"conditions": [{"fieldId": "name", "comparison": "IS_NOT_EMPTY"}]},
        "then": {"required": True},
    }
    spec = {
        **SPEC,
        "pages": [{"id": "page-1", "fields": [name, {**dinner, "rules": [rule]}]}],
    }
    url = f"{API}/workspaces/{workspace.id}/forms/validate"
    for enabled in (False, True):
        monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", enabled)
        response = await client.post(url, json=spec, cookies=test_user_cookies)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is True, body["errors"]
        warned = [w for w in body["warnings"] if w["path"].endswith("/rules")]
        assert bool(warned) is (not enabled)


async def test_mcp_update_form_follows_the_flag(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    token = await _make_key(workspace.id, ["forms:read", "forms:write"])
    ops = [
        {
            "op": "add_field",
            "pageId": "page-1",
            "ref": "other",
            "field": {"title": "Other", "type": "short_text"},
        },
        {
            "op": "set_field_rules",
            "fieldId": "field-1",
            "rules": [
                {
                    "id": "r1",
                    "when": {
                        "conditions": [
                            {"fieldId": "$ref:other", "comparison": "IS_NOT_EMPTY"}
                        ]
                    },
                    "then": {"required": True},
                }
            ],
        },
    ]
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", False)
    result = _tool_text(
        await _call_tool(
            client,
            token,
            "update_form",
            {"form_id": workspace_form.form_id, "ops": ops, "atomic": True},
        )
    )
    assert result["applied"] is False
    assert "FIELD_RULES_ENABLED" in result["results"][1]["message"]
    stored = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert len(stored.fields[0].properties.fields) == 1
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    result = _tool_text(
        await _call_tool(
            client,
            token,
            "update_form",
            {"form_id": workspace_form.form_id, "ops": ops, "atomic": True},
        )
    )
    assert result["applied"] is True, result
    stored = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    first, other = stored.fields[0].properties.fields
    assert first.properties.rules[0].when.conditions[0].field_id == other.id
