"""The switch for the newer question types (NEW_QUESTION_TYPES_ENABLED,
services/new_question_types.py) on every write path: the builder save, the
public spec API, the edit operations (public API and MCP), MCP form creation,
templates, a copy of a form, and the workspace permissions answer. Each runs
with the switch on and off. What a form already has keeps working while it is
off: its questions are saved unchanged, answered and exported."""

import json

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.config import settings
from tests.app.controllers.data import testUser
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
CODE = "question_type_disabled"


def _switch(monkeypatch, on):
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", on)


def _page(fields):
    return {
        "id": "page-1",
        "index": 0,
        "type": "slide",
        "properties": {"fields": fields},
    }


def _body(fields):
    return {"title": "Typed", "builderVersion": "v2", "fields": [_page(fields)]}


def _short(field_id="a"):
    return {"id": field_id, "type": "short_text", "title": field_id}


def _time(title="Arrival", **properties):
    return {"id": "t", "type": "time", "title": title, "properties": properties}


def _money(**properties):
    return {"id": "m", "type": "currency", "title": "Budget", "properties": properties}


def _day(**properties):
    return {"id": "d", "type": "day", "title": "Born", "properties": properties}


def _stay(**properties):
    return {"id": "r", "type": "date_range", "title": "Stay", "properties": properties}


def _tags(**validations):
    return {"id": "g", "type": "tags", "title": "Topics", "validations": validations}


async def _save(client, workspace, form, cookies, fields):
    return await client.patch(
        f"{API}/workspaces/{workspace.id}/forms/{form.form_id}",
        cookies=cookies,
        data={"form_body": json.dumps(_body(fields))},
    )


# --- the builder save ----------------------------------------------------------------


@pytest.mark.parametrize("kind", ["time", "day", "currency", "date_range", "tags"])
async def test_the_builder_save_refuses_a_new_question_while_off(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch, kind
):
    question = {
        "time": _time(),
        "day": _day(),
        "currency": _money(),
        "date_range": _stay(),
        "tags": _tags(),
    }[kind]
    _switch(monkeypatch, False)
    response = await _save(
        client, workspace, workspace_form, test_user_cookies, [_short(), question]
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == CODE
    assert [(e["fieldId"], e["type"]) for e in body["errors"]] == [
        (question["id"], kind)
    ]
    assert "NEW_QUESTION_TYPES_ENABLED" in body["message"]
    stored = await container.form_service().get_form_document_by_id(
        workspace_form.form_id
    )
    stored_types = [
        f.type.value
        for page in stored.fields or []
        for f in (page.properties.fields or [] if page.properties else [])
    ]
    assert kind not in stored_types
    # on: the same save is accepted
    _switch(monkeypatch, True)
    response = await _save(
        client, workspace, workspace_form, test_user_cookies, [_short(), question]
    )
    assert response.status_code == 200, response.text


async def test_questions_a_form_has_keep_saving_while_off(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    fields = [
        _short(),
        _time(minTime="08:00", maxTime="18:00"),
        _money(currencies=["EUR"]),
        _day(),
        _stay(dateRules=[{"comparison": "after", "target": "today"}]),
        _tags(maxChoices=3),
    ]
    _switch(monkeypatch, True)
    response = await _save(client, workspace, workspace_form, test_user_cookies, fields)
    assert response.status_code == 200, response.text
    _switch(monkeypatch, False)
    # the same questions again, a new title, another question, a new place
    fields[1]["title"] = "Arrival time"
    fields[0]["title"] = "Another"
    fields.append(_short("b"))
    fields.reverse()
    response = await _save(client, workspace, workspace_form, test_user_cookies, fields)
    assert response.status_code == 200, response.text
    # settings changed: refused, and the form keeps what it had
    changed = json.loads(json.dumps(fields))
    for field in changed:
        if field["id"] == "t":
            field["properties"]["minTime"] = "09:00"
    response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
    assert response.status_code == 422 and response.json()["code"] == CODE
    assert [(e["fieldId"], e["type"]) for e in response.json()["errors"]] == [
        ("t", "time")
    ]
    changed = json.loads(json.dumps(fields))
    for field in changed:
        if field["id"] == "m":
            field["properties"]["currencies"] = ["EUR", "USD"]
    response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
    assert response.status_code == 422 and response.json()["code"] == CODE
    # new date rules on a range, a new number of tags: refused
    for field_id, edit in (
        ("r", lambda f: f["properties"].__setitem__("dateRules", [{"comparison": "before", "target": "today"}])),
        ("g", lambda f: f["validations"].__setitem__("maxChoices", 5)),
        ("g", lambda f: f["validations"].__setitem__("maxLength", 10)),
    ):
        changed = json.loads(json.dumps(fields))
        for field in changed:
            if field["id"] == field_id:
                edit(field)
        response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
        assert response.status_code == 422 and response.json()["code"] == CODE
        assert [e["fieldId"] for e in response.json()["errors"]] == [field_id]
    # a question turned into one of the new types: refused
    changed = json.loads(json.dumps(fields))
    for field in changed:
        if field["id"] == "b":
            field["type"] = "currency"
    response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
    assert response.status_code == 422 and response.json()["code"] == CODE
    # one of them turned into an older type, or removed: allowed
    changed = [f for f in fields if f["id"] != "t"]
    changed[0]["type"] = "short_text"
    response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
    assert response.status_code == 200, response.text


async def test_deleting_the_date_question_a_day_rule_points_at_does_not_strand_the_day_question(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    start = {"id": "s", "type": "date", "title": "Start", "properties": {}}
    rule = {"comparison": "after", "target": "field", "fieldId": "s"}
    day = _day(dateRules=[rule, {"comparison": "before", "target": "today"}])
    _switch(monkeypatch, True)
    response = await _save(client, workspace, workspace_form, test_user_cookies, [start, day])
    assert response.status_code == 200, response.text
    _switch(monkeypatch, False)
    # the builder removes the date question and the rule that read it: allowed
    day_after = _day(dateRules=[{"comparison": "before", "target": "today"}])
    response = await _save(client, workspace, workspace_form, test_user_cookies, [day_after])
    assert response.status_code == 200, response.text
    # a date rule that was not there is new
    added = _day(dateRules=[{"comparison": "before", "target": "today"}, {"comparison": "after", "target": "date", "date": "1900-01-01"}])
    response = await _save(client, workspace, workspace_form, test_user_cookies, [added])
    assert response.status_code == 422 and response.json()["code"] == CODE


# --- creating a form, a copy, a template ------------------------------------------


async def test_creating_a_form_follows_the_switch_and_a_copy_keeps_its_questions(
    workspace, monkeypatch
):
    service = container.workspace_form_service()
    from backend.app.controllers.workspace_forms import _parse_form_body

    def body():
        return _parse_form_body(json.dumps(_body([_short(), _time(minTime="08:00")])))

    _switch(monkeypatch, False)
    with pytest.raises(Exception) as error:
        await service.create_form(workspace.id, body(), testUser)
    assert error.value.status_code == 422
    assert error.value.content["code"] == CODE
    _switch(monkeypatch, True)
    created = await service.create_form(workspace.id, body(), testUser)
    # a copy (a template's or a form's) keeps what its source has
    _switch(monkeypatch, False)
    copy = await service.create_form(
        workspace.id, body(), testUser, drop_unusable_settings=True
    )
    stored = await container.form_service().get_form_document_by_id(copy.form_id)
    assert [f.type.value for f in stored.fields[0].properties.fields] == [
        "short_text",
        "time",
    ]
    assert created.form_id != copy.form_id


async def test_a_template_follows_the_switch(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    template = {"title": "T", "fields": [_page([_short(), _time()])]}
    url = f"{API}/workspaces/{workspace.id}/template"
    _switch(monkeypatch, False)
    response = await client.post(
        url, cookies=test_user_cookies, data={"template_body": json.dumps(template)}
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == CODE
    _switch(monkeypatch, True)
    response = await client.post(
        url, cookies=test_user_cookies, data={"template_body": json.dumps(template)}
    )
    assert response.status_code != 422, response.text


# --- the public API -------------------------------------------------------------------


def _spec_with(*questions):
    page = SPEC["pages"][0]
    return {**SPEC, "pages": [{**page, "fields": [*page["fields"], *questions]}]}


async def test_the_spec_api_follows_the_switch(
    client: AsyncClient, workspace, monkeypatch
):
    token = await _token(workspace.id)
    spec = _spec_with({"id": "at", "type": "time", "title": "Arrival"})
    _switch(monkeypatch, False)
    body = _is_error(
        await client.post(f"{PUBLIC}/forms", json=spec, headers=_auth(token)),
        422,
        CODE,
    )
    assert "NEW_QUESTION_TYPES_ENABLED" in body["message"]
    _switch(monkeypatch, True)
    response = await client.post(f"{PUBLIC}/forms", json=spec, headers=_auth(token))
    assert response.status_code == 201, response.text
    form_id = response.json()["formId"]
    url = f"{PUBLIC}/forms/{form_id}"
    # off again: the document read back can be saved again (with a new
    # title), but a new question or a changed setting is refused
    _switch(monkeypatch, False)
    fetched = await client.get(url, headers=_auth(token))
    assert fetched.status_code == 200
    document = fetched.json()
    etag = fetched.headers["ETag"]
    assert "time" in [f["type"] for f in document["pages"][0]["fields"]]
    renamed = {**document, "title": "Renamed"}
    replaced = await client.put(
        url, json=renamed, headers=_auth(token, **{"If-Match": etag})
    )
    assert replaced.status_code == 200, replaced.text
    etag = replaced.headers["ETag"]
    changed = json.loads(json.dumps(replaced.json()))
    for field in changed["pages"][0]["fields"]:
        if field["type"] == "time":
            field["minTime"] = "09:00"
    body = _is_error(
        await client.put(url, json=changed, headers=_auth(token, **{"If-Match": etag})),
        422,
        CODE,
    )
    assert "NEW_QUESTION_TYPES_ENABLED" in body["message"], body
    assert "t" in json.dumps(body["errors"]) and "time" in json.dumps(body["errors"]), body
    added = json.loads(json.dumps(replaced.json()))
    added["pages"][0]["fields"].append({"id": "pay", "type": "currency", "title": "Pay"})
    _is_error(
        await client.put(url, json=added, headers=_auth(token, **{"If-Match": etag})),
        422,
        CODE,
    )


async def test_the_validate_endpoint_warns_while_off(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    spec = _spec_with(
        {"id": "at", "type": "time", "title": "Arrival"},
        {"id": "pay", "type": "currency", "title": "Budget"},
    )
    url = f"{API}/workspaces/{workspace.id}/forms/validate"
    for enabled in (False, True):
        _switch(monkeypatch, enabled)
        response = await client.post(url, json=spec, cookies=test_user_cookies)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is True, body["errors"]
        warned = [w for w in body["warnings"] if "switched off" in w["message"]]
        assert bool(warned) is (not enabled)
        if warned:
            assert len(warned) == 2


OPS = [
    {
        "op": "add_field",
        "pageId": "page-1",
        "field": {"title": "Arrival", "type": "time"},
    }
]


async def test_the_public_api_ops_follow_the_switch(
    client: AsyncClient, workspace, monkeypatch
):
    token = await _token(workspace.id)
    form_id = (await _create(client, token, SPEC)).json()["formId"]
    url = f"{PUBLIC}/forms/{form_id}/ops"
    _switch(monkeypatch, False)
    body = _is_error(
        await client.post(url, json={"ops": OPS}, headers=_auth(token)),
        422,
        "ops_failed",
    )
    assert "NEW_QUESTION_TYPES_ENABLED" in body["errors"][0]["message"]
    stored = await container.form_repo().get_form_document_by_id(form_id)
    assert all(f.type.value != "time" for f in stored.fields[0].properties.fields)
    dry = await client.post(
        f"{url}/dry-run", json={"ops": OPS, "atomic": False}, headers=_auth(token)
    )
    assert dry.status_code == 200 and dry.json()["results"][0]["ok"] is False
    _switch(monkeypatch, True)
    response = await client.post(url, json={"ops": OPS}, headers=_auth(token))
    assert response.status_code == 200, response.text
    stored = await container.form_repo().get_form_document_by_id(form_id)
    assert any(f.type.value == "time" for f in stored.fields[0].properties.fields)
    # off again: a new title on that question still applies, a new limit does not
    time_id = next(
        f.id for f in stored.fields[0].properties.fields if f.type.value == "time"
    )
    _switch(monkeypatch, False)
    rename = [{"op": "update_field", "fieldId": time_id, "patch": {"title": "Arrives"}}]
    response = await client.post(url, json={"ops": rename}, headers=_auth(token))
    assert response.status_code == 200, response.text
    limit = [{"op": "update_field", "fieldId": time_id, "patch": {"minTime": "08:00"}}]
    _is_error(
        await client.post(url, json={"ops": limit}, headers=_auth(token)),
        422,
        "ops_failed",
    )


# --- MCP ------------------------------------------------------------------------------


async def test_mcp_update_form_follows_the_switch(
    client: AsyncClient, workspace, workspace_form, monkeypatch
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    token = await _make_key(workspace.id, ["forms:read", "forms:write"])
    args = {"form_id": workspace_form.form_id, "ops": OPS, "atomic": True}
    _switch(monkeypatch, False)
    result = _tool_text(await _call_tool(client, token, "update_form", args))
    assert result["applied"] is False
    assert "NEW_QUESTION_TYPES_ENABLED" in result["results"][0]["message"]
    stored = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert len(stored.fields[0].properties.fields) == 1
    dry = _tool_text(await _call_tool(client, token, "dry_run_ops", args))
    assert dry["results"][0]["ok"] is False
    _switch(monkeypatch, True)
    result = _tool_text(await _call_tool(client, token, "update_form", args))
    assert result["applied"] is True, result
    stored = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert [f.type.value for f in stored.fields[0].properties.fields][-1] == "time"


# --- the permissions answer and the assistant ---------------------------------------


async def test_the_permissions_answer_tells_the_builder(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    url = f"{API}/workspaces/{workspace.id}/permissions"
    for enabled in (False, True):
        _switch(monkeypatch, enabled)
        response = await client.get(url, cookies=test_user_cookies)
        assert response.status_code == 200, response.text
        assert response.json()["newQuestionTypesEnabled"] is enabled


def test_the_switch_is_off_by_default_and_listed():
    from backend.config.application import Application

    assert Application.model_fields["NEW_QUESTION_TYPES_ENABLED"].default is False


def test_the_assistant_is_told_about_the_types_only_while_they_are_on(monkeypatch):
    from backend.app.services.ai.prompt_builder import ops_guide

    _switch(monkeypatch, False)
    off = ops_guide()
    assert "currency" not in off.split("Field types you may create")[1].split("\n\n")[0]
    assert "phone_number, date, yes_no" in off
    _switch(monkeypatch, True)
    on = ops_guide()
    assert "currency (an amount" in on and "time (HH:MM" in on


# --- the date range and tags types through the operations ----------------------------


@pytest.mark.parametrize("kind", ["date_range", "tags"])
async def test_the_public_api_ops_follow_the_switch_for_ranges_and_tags(
    client: AsyncClient, workspace, monkeypatch, kind
):
    ops = [{"op": "add_field", "pageId": "page-1", "field": {"title": "New", "type": kind}}]
    token = await _token(workspace.id)
    form_id = (await _create(client, token, SPEC)).json()["formId"]
    url = f"{PUBLIC}/forms/{form_id}/ops"
    _switch(monkeypatch, False)
    body = _is_error(
        await client.post(url, json={"ops": ops}, headers=_auth(token)), 422, "ops_failed"
    )
    assert "NEW_QUESTION_TYPES_ENABLED" in body["errors"][0]["message"]
    _switch(monkeypatch, True)
    response = await client.post(url, json={"ops": ops}, headers=_auth(token))
    assert response.status_code == 200, response.text
    stored = await container.form_repo().get_form_document_by_id(form_id)
    added = next(f for f in stored.fields[0].properties.fields if f.type.value == kind)
    # off again: a title edit applies, new limits do not
    _switch(monkeypatch, False)
    rename = [{"op": "update_field", "fieldId": added.id, "patch": {"title": "Renamed"}}]
    assert (await client.post(url, json={"ops": rename}, headers=_auth(token))).status_code == 200
    if kind == "tags":
        change = [{"op": "set_field_validation", "fieldId": added.id, "validation": {"maxChoices": 4}}]
    else:
        change = [
            {
                "op": "update_field",
                "fieldId": added.id,
                "patch": {"dateRules": [{"comparison": "after", "target": "today"}]},
            }
        ]
    _is_error(
        await client.post(url, json={"ops": change}, headers=_auth(token)), 422, "ops_failed"
    )


@pytest.mark.parametrize("kind", ["date_range", "tags"])
async def test_mcp_update_form_follows_the_switch_for_ranges_and_tags(
    client: AsyncClient, workspace, workspace_form, monkeypatch, kind
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    token = await _make_key(workspace.id, ["forms:read", "forms:write"])
    ops = [{"op": "add_field", "pageId": "page-1", "field": {"title": "New", "type": kind}}]
    args = {"form_id": workspace_form.form_id, "ops": ops, "atomic": True}
    _switch(monkeypatch, False)
    result = _tool_text(await _call_tool(client, token, "update_form", args))
    assert result["applied"] is False
    assert "NEW_QUESTION_TYPES_ENABLED" in result["results"][0]["message"]
    _switch(monkeypatch, True)
    result = _tool_text(await _call_tool(client, token, "update_form", args))
    assert result["applied"] is True, result


@pytest.mark.parametrize("kind", ["date_range", "tags"])
async def test_the_spec_api_follows_the_switch_for_ranges_and_tags(
    client: AsyncClient, workspace, monkeypatch, kind
):
    token = await _token(workspace.id)
    spec = _spec_with({"id": "x", "type": kind, "title": "New"})
    _switch(monkeypatch, False)
    _is_error(await client.post(f"{PUBLIC}/forms", json=spec, headers=_auth(token)), 422, CODE)
    _switch(monkeypatch, True)
    response = await client.post(f"{PUBLIC}/forms", json=spec, headers=_auth(token))
    assert response.status_code == 201, response.text
    fetched = await client.get(f"{PUBLIC}/forms/{response.json()['formId']}", headers=_auth(token))
    assert kind in [f["type"] for f in fetched.json()["pages"][0]["fields"]]
