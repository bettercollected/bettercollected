"""The switch of the address question (ADDRESS_QUESTION_ENABLED,
services/new_question_types.py) on every write path: the builder save, the
public spec API, the edit operations (public API and MCP), a copy of a form, a
template, the spec's validate warning and the workspace permissions answer.
Each runs with the switch on and off, and the answer is the question's own
code (422 ``address_question_disabled``), not the other types'. What a form
already has keeps working while it is off."""

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
CODE = "address_question_disabled"


def _switch(monkeypatch, on):
    monkeypatch.setattr(settings, "ADDRESS_QUESTION_ENABLED", on)


def _page(fields):
    return {"id": "page-1", "index": 0, "type": "slide", "properties": {"fields": fields}}


def _body(fields):
    return {"title": "Where", "builderVersion": "v2", "fields": [_page(fields)]}


def _short(field_id="a"):
    return {"id": field_id, "type": "short_text", "title": field_id}


def _address(**properties):
    return {"id": "ad", "type": "address", "title": "Where do you live?", "properties": properties}


async def _save(client, workspace, form, cookies, fields):
    return await client.patch(
        f"{API}/workspaces/{workspace.id}/forms/{form.form_id}",
        cookies=cookies,
        data={"form_body": json.dumps(_body(fields))},
    )


def _types(stored):
    return [
        f.type.value
        for page in stored.fields or []
        for f in (page.properties.fields or [] if page.properties else [])
    ]


async def test_the_builder_save_refuses_a_new_address_question_while_off(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    _switch(monkeypatch, False)
    response = await _save(client, workspace, workspace_form, test_user_cookies, [_short(), _address()])
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == CODE
    assert [(e["fieldId"], e["type"]) for e in body["errors"]] == [("ad", "address")]
    assert "ADDRESS_QUESTION_ENABLED" in body["message"]
    stored = await container.form_service().get_form_document_by_id(workspace_form.form_id)
    assert "address" not in _types(stored)
    _switch(monkeypatch, True)
    response = await _save(client, workspace, workspace_form, test_user_cookies, [_short(), _address()])
    assert response.status_code == 200, response.text


async def test_the_other_types_switch_does_not_open_the_address_question(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    _switch(monkeypatch, False)
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)
    response = await _save(client, workspace, workspace_form, test_user_cookies, [_address()])
    assert response.status_code == 422 and response.json()["code"] == CODE
    # and the address switch does not open the other types
    _switch(monkeypatch, True)
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
    time = {"id": "t", "type": "time", "title": "Arrival"}
    response = await _save(client, workspace, workspace_form, test_user_cookies, [time])
    assert response.status_code == 422 and response.json()["code"] == "question_type_disabled"


async def test_an_address_question_a_form_has_keeps_saving_while_off(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    fields = [_short(), _address(countries=["NL", "BE"], addressLookup=False)]
    _switch(monkeypatch, True)
    response = await _save(client, workspace, workspace_form, test_user_cookies, fields)
    assert response.status_code == 200, response.text
    _switch(monkeypatch, False)
    # a new title, another question, a new place: fine
    fields[1]["title"] = "Home address"
    fields[0]["title"] = "Another"
    fields.append(_short("b"))
    fields.reverse()
    response = await _save(client, workspace, workspace_form, test_user_cookies, fields)
    assert response.status_code == 200, response.text
    # a changed setting: refused, and so is a question turned into an address
    for edit in (
        lambda f: f["properties"].__setitem__("countries", ["NL"]),
        lambda f: f["properties"].__setitem__("addressLookup", True),
    ):
        changed = json.loads(json.dumps(fields))
        edit(next(f for f in changed if f["id"] == "ad"))
        response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
        assert response.status_code == 422 and response.json()["code"] == CODE
    changed = json.loads(json.dumps(fields))
    next(f for f in changed if f["id"] == "b")["type"] = "address"
    response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
    assert response.status_code == 422 and response.json()["code"] == CODE
    # removed, or turned into an older type: allowed
    changed = [f for f in fields if f["id"] != "ad"]
    response = await _save(client, workspace, workspace_form, test_user_cookies, changed)
    assert response.status_code == 200, response.text


async def test_the_countries_of_a_question_are_checked_on_save(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, monkeypatch
):
    _switch(monkeypatch, True)
    for countries in ([], ["XX"], ["nl"], ["NL", "NL"], ["NL"] * 31):
        response = await _save(
            client, workspace, workspace_form, test_user_cookies, [_address(countries=countries)]
        )
        assert response.status_code == 422, (countries, response.text)


async def test_creating_a_form_follows_the_switch_and_a_copy_keeps_its_questions(
    workspace, monkeypatch
):
    from backend.app.controllers.workspace_forms import _parse_form_body

    service = container.workspace_form_service()

    def body():
        return _parse_form_body(json.dumps(_body([_short(), _address()])))

    _switch(monkeypatch, False)
    with pytest.raises(Exception) as error:
        await service.create_form(workspace.id, body(), testUser)
    assert error.value.status_code == 422
    assert error.value.content["code"] == CODE
    _switch(monkeypatch, True)
    created = await service.create_form(workspace.id, body(), testUser)
    _switch(monkeypatch, False)
    copy = await service.create_form(workspace.id, body(), testUser, drop_unusable_settings=True)
    stored = await container.form_service().get_form_document_by_id(copy.form_id)
    assert _types(stored) == ["short_text", "address"]
    assert created.form_id != copy.form_id


async def test_a_template_follows_the_switch(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    template = {"title": "T", "fields": [_page([_short(), _address()])]}
    url = f"{API}/workspaces/{workspace.id}/template"
    _switch(monkeypatch, False)
    response = await client.post(url, cookies=test_user_cookies, data={"template_body": json.dumps(template)})
    assert response.status_code == 422, response.text
    assert response.json()["code"] == CODE
    _switch(monkeypatch, True)
    response = await client.post(url, cookies=test_user_cookies, data={"template_body": json.dumps(template)})
    assert response.status_code != 422, response.text


def _spec_with(*questions):
    page = SPEC["pages"][0]
    return {**SPEC, "pages": [{**page, "fields": [*page["fields"], *questions]}]}


async def test_the_spec_api_follows_the_switch_and_round_trips_the_settings(
    client: AsyncClient, workspace, monkeypatch
):
    token = await _token(workspace.id)
    question = {
        "id": "ad",
        "type": "address",
        "title": "Home",
        "countries": ["NL", "BE"],
        "addressLookup": False,
    }
    spec = _spec_with(question)
    _switch(monkeypatch, False)
    body = _is_error(await client.post(f"{PUBLIC}/forms", json=spec, headers=_auth(token)), 422, CODE)
    assert "ADDRESS_QUESTION_ENABLED" in body["message"]
    _switch(monkeypatch, True)
    response = await client.post(f"{PUBLIC}/forms", json=spec, headers=_auth(token))
    assert response.status_code == 201, response.text
    form_id = response.json()["formId"]
    fetched = await client.get(f"{PUBLIC}/forms/{form_id}", headers=_auth(token))
    stored = next(f for f in fetched.json()["pages"][0]["fields"] if f["type"] == "address")
    assert stored["countries"] == ["NL", "BE"] and stored["addressLookup"] is False
    # off again: a new title is fine, a new setting is refused
    _switch(monkeypatch, False)
    document = fetched.json()
    etag = fetched.headers["ETag"]
    url = f"{PUBLIC}/forms/{form_id}"
    renamed = {**document, "title": "Renamed"}
    replaced = await client.put(url, json=renamed, headers=_auth(token, **{"If-Match": etag}))
    assert replaced.status_code == 200, replaced.text
    changed = json.loads(json.dumps(replaced.json()))
    for field in changed["pages"][0]["fields"]:
        if field["type"] == "address":
            field["countries"] = ["NL"]
    _is_error(
        await client.put(url, json=changed, headers=_auth(token, **{"If-Match": replaced.headers["ETag"]})),
        422,
        CODE,
    )


@pytest.mark.parametrize(
    "field",
    [
        {"id": "ad", "type": "address", "title": "Home", "countries": []},
        {"id": "ad", "type": "address", "title": "Home", "countries": ["ZZ"]},
        {"id": "ad", "type": "address", "title": "Home", "countries": ["NL", "NL"]},
        {"id": "ad", "type": "address", "title": "Home", "addressLookup": "maybe"},
    ],
)
async def test_the_spec_refuses_bad_settings(client: AsyncClient, workspace, monkeypatch, field):
    _switch(monkeypatch, True)
    token = await _token(workspace.id)
    response = await client.post(f"{PUBLIC}/forms", json=_spec_with(field), headers=_auth(token))
    assert response.status_code == 422, response.text


async def test_the_validate_endpoint_warns_while_off(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    spec = _spec_with({"id": "ad", "type": "address", "title": "Home"})
    url = f"{API}/workspaces/{workspace.id}/forms/validate"
    for enabled in (False, True):
        _switch(monkeypatch, enabled)
        response = await client.post(url, json=spec, cookies=test_user_cookies)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is True, body["errors"]
        warned = [w for w in body["warnings"] if "ADDRESS_QUESTION_ENABLED" in w["message"]]
        assert bool(warned) is (not enabled)


OPS = [
    {
        "op": "add_field",
        "pageId": "page-1",
        "field": {"title": "Home", "type": "address", "countries": ["NL", "DE"], "addressLookup": False},
    }
]


async def test_the_public_api_ops_follow_the_switch(client: AsyncClient, workspace, monkeypatch):
    token = await _token(workspace.id)
    form_id = (await _create(client, token, SPEC)).json()["formId"]
    url = f"{PUBLIC}/forms/{form_id}/ops"
    _switch(monkeypatch, False)
    body = _is_error(await client.post(url, json={"ops": OPS}, headers=_auth(token)), 422, "ops_failed")
    assert "ADDRESS_QUESTION_ENABLED" in body["errors"][0]["message"]
    stored = await container.form_repo().get_form_document_by_id(form_id)
    assert all(f.type.value != "address" for f in stored.fields[0].properties.fields)
    dry = await client.post(f"{url}/dry-run", json={"ops": OPS, "atomic": False}, headers=_auth(token))
    assert dry.status_code == 200 and dry.json()["results"][0]["ok"] is False
    _switch(monkeypatch, True)
    response = await client.post(url, json={"ops": OPS}, headers=_auth(token))
    assert response.status_code == 200, response.text
    stored = await container.form_repo().get_form_document_by_id(form_id)
    added = next(f for f in stored.fields[0].properties.fields if f.type.value == "address")
    assert added.properties.countries == ["NL", "DE"] and added.properties.address_lookup is False
    # off again: a new title still applies, a new setting does not
    _switch(monkeypatch, False)
    rename = [{"op": "update_field", "fieldId": added.id, "patch": {"title": "Where to?"}}]
    assert (await client.post(url, json={"ops": rename}, headers=_auth(token))).status_code == 200
    change = [{"op": "update_field", "fieldId": added.id, "patch": {"countries": ["NL"]}}]
    _is_error(await client.post(url, json={"ops": change}, headers=_auth(token)), 422, "ops_failed")
    _switch(monkeypatch, True)
    # countries and the lookup only belong to an address question, and are checked
    bad = [
        {"op": "update_field", "fieldId": added.id, "patch": {"countries": ["XX"]}},
    ]
    _is_error(await client.post(url, json={"ops": bad}, headers=_auth(token)), 422, "ops_failed")
    short_id = next(f.id for f in stored.fields[0].properties.fields if f.type.value != "address")
    wrong = [{"op": "update_field", "fieldId": short_id, "patch": {"addressLookup": True}}]
    _is_error(await client.post(url, json={"ops": wrong}, headers=_auth(token)), 422, "ops_failed")


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
    assert "ADDRESS_QUESTION_ENABLED" in result["results"][0]["message"]
    _switch(monkeypatch, True)
    result = _tool_text(await _call_tool(client, token, "update_form", args))
    assert result["applied"] is True, result
    stored = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    assert [f.type.value for f in stored.fields[0].properties.fields][-1] == "address"


async def test_the_permissions_answer_tells_the_builder(
    client: AsyncClient, workspace, test_user_cookies, monkeypatch
):
    url = f"{API}/workspaces/{workspace.id}/permissions"
    for enabled in (False, True):
        _switch(monkeypatch, enabled)
        response = await client.get(url, cookies=test_user_cookies)
        assert response.status_code == 200, response.text
        assert response.json()["addressQuestionEnabled"] is enabled
        # the lookup also needs its own switch
        assert response.json()["addressLookupEnabled"] is False
    monkeypatch.setattr(settings, "ADDRESS_LOOKUP_ENABLED", True)
    _switch(monkeypatch, True)
    assert (await client.get(url, cookies=test_user_cookies)).json()["addressLookupEnabled"] is True
    _switch(monkeypatch, False)
    assert (await client.get(url, cookies=test_user_cookies)).json()["addressLookupEnabled"] is False


def test_the_switches_are_off_by_default():
    from backend.config.application import Application

    assert Application.model_fields["ADDRESS_QUESTION_ENABLED"].default is False
    assert Application.model_fields["ADDRESS_LOOKUP_ENABLED"].default is False


def test_the_assistant_is_told_about_the_address_question_only_while_it_is_on(monkeypatch):
    from backend.app.services.ai.prompt_builder import ops_guide

    _switch(monkeypatch, False)
    assert "address (a postal address" not in ops_guide()
    _switch(monkeypatch, True)
    assert "address (a postal address" in ops_guide()
