"""``CAPTCHA_ENABLED``: the server switch, off until the release. Off means the
challenge route answers 404, the header is never read, forms are served without
the setting, creators cannot change the per-form setting (422
``captcha_disabled``) and nothing is recorded: behaviour as before."""

import copy
from unittest.mock import patch

import pytest
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.captcha import challenge as ch
from backend.app.services.captcha.mode import DISABLED_CODE, DISABLED_MESSAGE
from backend.app.services.form_spec.checks import check_spec_document
from backend.config import settings
from tests.app.captcha.conftest import ALICE, a_form, ask, submit
from tests.app.controllers.data import testUser
from tests.app.controllers.test_form_spec_api import VALID
from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text
from tests.app.controllers.test_form_spec_api import _make_v2

pytestmark = pytest.mark.usefixtures("off")

ON = {"op": "update_form_settings", "patch": {"captchaEnabled": False}}


def test_the_switch_is_off_by_default():
    from backend.config.application import Application

    assert Application.model_fields["CAPTCHA_ENABLED"].default is False


def test_the_tuning_settings_have_the_documented_defaults_and_bounds():
    from backend.config.api_settings import ApiSettings

    assert ApiSettings.model_fields["CAPTCHA_BASE_BITS_SUBMIT"].default == 17
    assert ApiSettings.model_fields["CAPTCHA_DIFFICULTY_BOOST"].default == 0
    from common.settings.inventory import INVENTORY

    spec = {s.key: s for s in INVENTORY}
    assert (
        spec["CAPTCHA_ENABLED"].default is False
        and spec["CAPTCHA_ENABLED"].tier.name == "T2"
    )
    base = spec["API_CAPTCHA_BASE_BITS_SUBMIT"]
    assert (base.min_value, base.max_value) == (ch.MIN_BITS, ch.MAX_BITS)


async def test_the_challenge_route_answers_404_before_anything(client, workspace):
    form = await a_form(workspace)
    answer = await ask(client, workspace, form)
    assert answer.status_code == 404 and answer.json()["code"] == "captcha_off"
    # not even a body or a workspace is looked at: a malformed one answers 404 too
    junk = await client.post(
        f"/api/v1/workspaces/{workspace.id}/captcha/challenge", json={}, headers=ALICE
    )
    assert junk.status_code in (404, 422)
    spy_pressure = container.captcha_service().pressure
    assert not spy_pressure._asked._keys and not spy_pressure._issued._keys


async def test_the_header_is_never_read_on_a_submit(
    client, workspace, claims, monkeypatch
):
    form = await a_form(workspace)

    def boom(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("the proof was read")

    monkeypatch.setattr(ch, "check", boom)
    for proof in (None, "garbage", "a.b.c", "x" * 5000):
        sent = await submit(client, workspace, form, proof)
        assert sent.status_code == 200, sent.text
    assert claims == []
    pressure = container.captcha_service().pressure
    assert not pressure._failed._keys and not pressure._submits._keys


async def test_nothing_is_recorded_while_off(client, workspace):
    form = await a_form(workspace)
    service = container.captcha_service()
    with patch.object(type(service), "note_submit") as noted, patch.object(
        type(service), "require"
    ) as required:
        assert (await submit(client, workspace, form, "x.y.z")).status_code == 200
    noted.assert_not_called()
    required.assert_not_called()


async def test_respondents_are_served_the_form_without_the_setting(
    client, workspace, test_user_cookies, monkeypatch
):
    form = await a_form(workspace)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    link.settings.captcha_enabled = False
    await container.workspace_form_repo().update(link.id, link)
    read = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}?published=true"
    off = (await client.get(read)).json()["settings"]
    assert "captchaRequired" not in off or off["captchaRequired"] is None
    assert not off.get("captchaEnabled")
    # what is stored stays
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    assert link.settings.captcha_enabled is False
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    on = (await client.get(read)).json()["settings"]
    assert on["captchaRequired"] is False


async def test_the_permissions_answer_says_it_is_off(
    client, workspace, test_user_cookies
):
    answer = await client.get(
        f"/api/v1/workspaces/{workspace.id}/permissions", cookies=test_user_cookies
    )
    assert answer.json()["captchaEnabled"] is False


def settings_url(workspace, form) -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/settings"


def refused_422(response) -> dict:
    assert response.status_code == 422, response.text
    content = response.json()
    assert content["code"] == DISABLED_CODE and content["message"] == DISABLED_MESSAGE
    return content


async def stored(workspace, form):
    return (
        await container.workspace_form_repo().find_workspace_form(
            workspace.id, form.form_id
        )
    ).settings


async def test_the_settings_patch_is_refused_and_changes_nothing(
    client, workspace, test_user_cookies
):
    form = await a_form(workspace)
    for value in (True, False):
        refused_422(
            await client.patch(
                settings_url(workspace, form),
                json={"captchaEnabled": value, "purpose": "Not stored either"},
                cookies=test_user_cookies,
            )
        )
    after = await stored(workspace, form)
    assert after.captcha_enabled is None and after.purpose is None
    # a patch that leaves it alone is fine
    assert (
        await client.patch(
            settings_url(workspace, form),
            json={"purpose": "Kept"},
            cookies=test_user_cookies,
        )
    ).status_code == 200


async def test_a_form_that_has_a_value_keeps_it_when_a_save_leaves_it_as_it_is(
    client, workspace, test_user_cookies
):
    form = await a_form(workspace)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    link.settings.captcha_enabled = False
    await container.workspace_form_repo().update(link.id, link)
    same = await client.patch(
        settings_url(workspace, form),
        json={"captchaEnabled": False, "purpose": "Saved"},
        cookies=test_user_cookies,
    )
    assert (
        same.status_code == 200 and same.json()["settings"]["captchaEnabled"] is False
    )
    refused_422(
        await client.patch(
            settings_url(workspace, form),
            json={"captchaEnabled": True},
            cookies=test_user_cookies,
        )
    )


def test_the_operations_engine_refuses_it():
    results = apply_form_ops(
        StandardForm(fields=[]),
        parse_ops([ON, {"op": "update_form_settings", "patch": {"purpose": "x"}}]),
    )[1]
    assert [r.ok for r in results] == [False, True]
    assert results[0].message == DISABLED_MESSAGE


def test_the_operations_engine_accepts_it_when_the_switch_is_on(monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    (result,) = apply_form_ops(StandardForm(fields=[]), parse_ops([ON]))[1]
    assert result.ok


async def test_the_ai_and_mcp_operations_refuse_it(client, workspace, workspace_form):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    key = await _make_key(workspace.id, ["forms:write"])
    result = _tool_text(
        await _call_tool(
            client, key, "update_form", {"form_id": workspace_form.form_id, "ops": [ON]}
        )
    )
    assert result["results"][0]["ok"] is False
    assert DISABLED_MESSAGE in result["results"][0]["message"]
    assert (await stored(workspace, workspace_form)).captcha_enabled is None


async def test_the_spec_api_refuses_a_document_that_sets_it(workspace):
    writer = container.form_spec_writer()
    document = copy.deepcopy(VALID)
    document["trust"] = {"captchaEnabled": False}
    with pytest.raises(HTTPException) as refused:
        await writer.create(workspace.id, document, testUser)
    assert refused.value.status_code == 422
    assert refused.value.content["code"] == DISABLED_CODE
    assert refused.value.content["errors"] == [
        {"path": "/trust/captchaEnabled", "message": DISABLED_MESSAGE}
    ]
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []
    document["trust"] = {}
    form_id, spec, etag = await writer.create(workspace.id, document, testUser)
    changed = copy.deepcopy(spec)
    changed["trust"] = {**(changed.get("trust") or {}), "captchaEnabled": False}
    with pytest.raises(HTTPException) as replaced:
        await writer.replace(workspace.id, form_id, changed, [etag], testUser)
    assert replaced.value.content["code"] == DISABLED_CODE
    preview = await writer.preview_replace(workspace.id, form_id, changed)
    assert (
        preview["valid"] is False
        and preview["errors"][-1]["path"] == "/trust/captchaEnabled"
    )


async def test_the_spec_api_accepts_it_when_the_switch_is_on(workspace, monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    document = copy.deepcopy(VALID)
    document["trust"] = {"captchaEnabled": False}
    form_id, spec, _ = await container.form_spec_writer().create(
        workspace.id, document, testUser
    )
    assert spec["trust"]["captchaEnabled"] is False


def test_validation_warns_about_it_while_the_switch_is_off(monkeypatch):
    document = copy.deepcopy(VALID)
    document["trust"] = {"captchaEnabled": False}
    warnings = check_spec_document(document)["warnings"]
    assert any(w["path"] == "/trust/captchaEnabled" for w in warnings)
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    assert not any(
        w["path"] == "/trust/captchaEnabled"
        for w in check_spec_document(document)["warnings"]
    )


async def test_copies_do_not_carry_the_setting(workspace, monkeypatch):
    form = await a_form(workspace)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    link.settings.captcha_enabled = False
    await container.workspace_form_repo().update(link.id, link)
    for enabled in (False, True):
        monkeypatch.setattr(settings, "CAPTCHA_ENABLED", enabled)
        copy_ = await container.workspace_form_service().duplicate_form(
            workspace.id, form.form_id, testUser
        )
        assert (await stored(workspace, copy_)).captcha_enabled is None
