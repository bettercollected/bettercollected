"""``SAVE_DRAFTS_ENABLED``: the server switch of the feature, off until it is
released. Off, turning a form's "save and continue later" setting on is refused
(422 ``save_drafts_disabled``) on every write path, and drafts are neither
saved nor opened; on, everything works. Discarding is always allowed."""

import copy
import json

import pytest
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.form_drafts.mode import DISABLED_CODE, DISABLED_MESSAGE
from backend.app.services.form_spec.checks import check_spec_document
from backend.config import settings
from tests.app.controllers.data import formData, testUser, testUser1
from tests.app.controllers.test_form_spec_api import VALID, _make_v2
from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text
from tests.app.controllers.test_public_api import BASE, _auth, _token
from tests.app.form_drafts.helpers import (
    body,
    cookies,
    draft_rows,
    drafting_form,
    settings_of,
    url,
)
from tests.app.registration.helpers import publish

pytestmark = pytest.mark.asyncio

ON = {"op": "update_form_settings", "patch": {"allowSaveDraft": True}}
OFF = {"op": "update_form_settings", "patch": {"allowSaveDraft": False}}


@pytest.fixture()
def switch_off(monkeypatch):
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", False)


def refused_422(response) -> dict:
    assert response.status_code == 422, response.text
    content = response.json()
    assert content["code"] == DISABLED_CODE and content["message"] == DISABLED_MESSAGE
    return content


async def stored(workspace, form):
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    return link.settings


def settings_url(workspace, form) -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/settings"


def test_the_switch_is_off_by_default():
    from backend.config.application import Application

    assert Application.model_fields["SAVE_DRAFTS_ENABLED"].default is False


async def test_the_permissions_answer_says_whether_it_is_on(
    client, workspace, test_user_cookies, monkeypatch
):
    for enabled in (True, False):
        monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", enabled)
        answer = await client.get(
            f"/api/v1/workspaces/{workspace.id}/permissions", cookies=test_user_cookies
        )
        assert answer.status_code == 200
        assert answer.json()["saveDraftsEnabled"] is enabled


# ---------------------------------------------------------------- write paths


async def test_the_settings_patch_refuses_turning_it_on_and_changes_nothing(
    client, workspace, test_user_cookies, switch_off
):
    form = await publish(workspace)
    refused = await client.patch(
        settings_url(workspace, form),
        json={"allowSaveDraft": True, "purpose": "Not stored either"},
        cookies=test_user_cookies,
    )
    refused_422(refused)
    after = await stored(workspace, form)
    assert not after.allow_save_draft and after.purpose is None
    # turning it off, or the days alone, is not turning it on
    assert (
        await client.patch(
            settings_url(workspace, form),
            json={"allowSaveDraft": False},
            cookies=test_user_cookies,
        )
    ).status_code == 200
    assert (
        await client.patch(
            settings_url(workspace, form),
            json={"draftRetentionDays": 14},
            cookies=test_user_cookies,
        )
    ).status_code == 200


async def test_the_settings_patch_turns_it_on_when_the_switch_is_on(
    client, workspace, test_user_cookies
):
    form = await publish(workspace)
    patched = await client.patch(
        settings_url(workspace, form),
        json={"allowSaveDraft": True},
        cookies=test_user_cookies,
    )
    assert (
        patched.status_code == 200
        and patched.json()["settings"]["allowSaveDraft"] is True
    )
    assert (await stored(workspace, form)).allow_save_draft is True


async def test_a_form_that_has_it_on_keeps_it_when_a_save_leaves_it_on(
    client, workspace, test_user_cookies, switch_off
):
    form = await publish(workspace)
    await settings_of(workspace, form, allow_save_draft=True)
    kept = await client.patch(
        settings_url(workspace, form),
        json={"allowSaveDraft": True, "purpose": "Saved"},
        cookies=test_user_cookies,
    )
    assert kept.status_code == 200 and kept.json()["settings"]["allowSaveDraft"] is True


def test_the_operations_engine_refuses_turning_it_on(switch_off):
    results = apply_form_ops(
        StandardForm(fields=[]),
        parse_ops(
            [
                ON,
                OFF,
                {"op": "update_form_settings", "patch": {"draftRetentionDays": 20}},
            ]
        ),
    )[1]
    assert [r.ok for r in results] == [False, True, True]
    assert results[0].message == DISABLED_MESSAGE


def test_the_operations_engine_turns_it_on_when_the_switch_is_on(monkeypatch):
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", True)
    (result,) = apply_form_ops(StandardForm(fields=[]), parse_ops([ON]))[1]
    assert result.ok


async def test_the_editor_ops_dry_run_and_the_public_api_ops_refuse_it(
    client, workspace, workspace_form, test_user_cookies, switch_off
):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    dry = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ops/dry-run",
        json={"ops": [ON]},
        cookies=test_user_cookies,
    )
    assert dry.status_code == 200
    result = dry.json()["results"][0]
    assert result["ok"] is False and result["message"] == DISABLED_MESSAGE
    token = await _token(workspace.id)
    api = await client.post(
        f"{BASE}/forms/{workspace_form.form_id}/ops",
        json={"ops": [ON]},
        headers=_auth(token),
    )
    assert api.status_code == 422, api.text
    assert api.json()["code"] == "ops_failed"
    assert api.json()["errors"][0]["message"] == DISABLED_MESSAGE
    assert not (await stored(workspace, workspace_form)).allow_save_draft


async def test_the_ai_and_mcp_operations_refuse_it(
    client, workspace, workspace_form, switch_off
):
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
    assert not (await stored(workspace, workspace_form)).allow_save_draft


async def test_the_spec_api_refuses_a_document_that_turns_it_on(workspace, switch_off):
    writer = container.form_spec_writer()
    document = copy.deepcopy(VALID)
    document["trust"] = {"allowSaveDraft": True}
    with pytest.raises(HTTPException) as refused:
        await writer.create(workspace.id, document, testUser)
    assert refused.value.status_code == 422
    assert refused.value.content["code"] == DISABLED_CODE
    assert refused.value.content["errors"] == [
        {"path": "/trust/allowSaveDraft", "message": DISABLED_MESSAGE}
    ]
    # nothing was created
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []
    # a document that leaves it out or off is fine
    document["trust"] = {"allowSaveDraft": False}
    form_id, spec, etag = await writer.create(workspace.id, document, testUser)
    # replacing with it on is refused, with it as it is passes
    on = copy.deepcopy(spec)
    on["trust"] = {**(on.get("trust") or {}), "allowSaveDraft": True}
    with pytest.raises(HTTPException) as replaced:
        await writer.replace(workspace.id, form_id, on, [etag], testUser)
    assert replaced.value.content["code"] == DISABLED_CODE
    preview = await writer.preview_replace(workspace.id, form_id, on)
    assert (
        preview["valid"] is False
        and preview["errors"][-1]["path"] == "/trust/allowSaveDraft"
    )
    assert not (
        await container.workspace_form_repo().find_workspace_form(workspace.id, form_id)
    ).settings.allow_save_draft


async def test_the_spec_api_accepts_it_when_the_switch_is_on(workspace):
    writer = container.form_spec_writer()
    document = copy.deepcopy(VALID)
    document["trust"] = {"allowSaveDraft": True, "draftRetentionDays": 20}
    form_id, spec, _ = await writer.create(workspace.id, document, testUser)
    assert (
        spec["trust"]["allowSaveDraft"] is True
        and spec["trust"]["draftRetentionDays"] == 20
    )


def test_validation_warns_about_it_while_the_switch_is_off(switch_off, monkeypatch):
    document = copy.deepcopy(VALID)
    document["trust"] = {"allowSaveDraft": True}
    warnings = check_spec_document(document)["warnings"]
    assert any(w["path"] == "/trust/allowSaveDraft" for w in warnings)
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", True)
    assert not any(
        w["path"] == "/trust/allowSaveDraft"
        for w in check_spec_document(document)["warnings"]
    )


async def test_copies_and_templates_never_carry_the_setting(
    workspace, switch_off, monkeypatch
):
    form = await drafting_form(workspace, draft_retention_days=20)
    for enabled in (False, True):
        monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", enabled)
        copy_ = await container.workspace_form_service().duplicate_form(
            workspace.id, form.form_id, testUser
        )
        link = await container.workspace_form_repo().find_workspace_form(
            workspace.id, copy_.form_id
        )
        assert (
            not link.settings.allow_save_draft
            and link.settings.draft_retention_days is None
        )
        template = await container.workspace_form_service().duplicate_form(
            workspace.id, form.form_id, testUser, is_template=True
        )
        assert not hasattr(template.settings, "allow_save_draft")


# ----------------------------------------------------------------- the runtime


async def test_while_off_a_draft_is_neither_saved_nor_opened(
    client, workspace, mails, monkeypatch
):
    form = await drafting_form(workspace)
    saved = await client.put(url(workspace, form), json=body(), cookies=cookies())
    sent = (
        await client.post(
            url(workspace, form, "/link"), json=body(email="ada@example.org")
        )
    ).json()
    from tests.app.form_drafts.helpers import token_of

    token = token_of(mails[0])
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", False)
    for call in (
        client.put(url(workspace, form), json=body(), cookies=cookies()),
        client.post(url(workspace, form, "/mine"), cookies=cookies()),
        client.post(url(workspace, form, "/open"), json={"token": token}),
        client.put(url(workspace, form), json=body(editKey=sent["editKey"])),
    ):
        assert (await call).status_code == 404
    refused = await client.post(
        url(workspace, form, "/link"), json=body(email="b@example.org")
    )
    assert refused.status_code == 404 and refused.json()["code"] == "drafts_off"
    assert len(mails) == 1 and saved.status_code == 200
    # erasure is never refused
    assert (
        await client.post(url(workspace, form, "/discard"), json={}, cookies=cookies())
    ).status_code == 200
    assert (
        await client.post(
            url(workspace, form, "/discard"), json={"editKey": sent["editKey"]}
        )
    ).status_code == 200
    assert await draft_rows() == []


async def test_while_off_the_purge_removes_every_draft(client, workspace, monkeypatch):
    from backend.jobs import tasks

    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", False)
    assert await tasks.purge_form_drafts(0) == "0 expired, 1 of forms that keep none"
    assert await draft_rows() == []


async def test_respondents_are_served_the_form_without_the_setting_while_off(
    client, workspace, monkeypatch
):
    form = await drafting_form(workspace, draft_retention_days=21)
    read_url = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}?published=true"
    on = (await client.get(read_url, cookies=cookies())).json()["settings"]
    assert on["allowSaveDraft"] is True and on["draftRetentionDays"] == 21
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", False)
    off = (await client.get(read_url, cookies=cookies())).json()["settings"]
    assert not off.get("allowSaveDraft") and not off.get("draftRetentionDays")
    # what is stored stays (the staff's settings read it)
    assert (await stored(workspace, form)).allow_save_draft is True


async def test_a_form_that_requires_sign_in_offers_no_link_with_the_switch_on_or_off(
    client, workspace, mails, monkeypatch
):
    """A form that requires a verified identity saves to the account only: no emailed link."""
    form = await drafting_form(workspace, require_verified_identity=True)
    for enabled in (True, False):
        monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", enabled)
        refused = await client.post(
            url(workspace, form, "/link"), json=body(email="ada@example.org")
        )
        assert refused.status_code == (403 if enabled else 404)
    assert mails == [] and await draft_rows() == []
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", True)
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).status_code == 200
    # no anonymous save either: there is no draft without an account or a link
    assert (await client.put(url(workspace, form), json=body())).status_code == 404
