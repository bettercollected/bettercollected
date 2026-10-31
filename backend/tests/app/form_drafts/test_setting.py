"""The per-form setting "Let respondents save and continue later": off by
default, changed with the settings PATCH, the ops engine and the form spec,
checked, and served to respondents (the privacy panel's retention)."""

import pytest
from common.form_spec import FormSpec, form_to_spec
from common.models.standard_form import StandardForm
from pydantic import ValidationError

from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.services.ai.ops import apply_form_ops, apply_settings_ops, parse_ops
from tests.app.controllers.data import testUser1
from tests.app.form_drafts.helpers import cookies, drafting_form, settings_of
from tests.app.registration.helpers import publish

pytestmark = pytest.mark.asyncio


def settings_url(workspace, form) -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/settings"


async def test_the_setting_is_off_by_default():
    assert WorkspaceFormSettings().allow_save_draft is None
    assert WorkspaceFormSettings().draft_retention_days is None


async def test_the_creator_turns_it_on_and_picks_the_days(
    client, workspace, test_user_cookies
):
    form = await publish(workspace)
    patched = await client.patch(
        settings_url(workspace, form),
        json={"allowSaveDraft": True, "draftRetentionDays": 14},
        cookies=test_user_cookies,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["settings"]["allowSaveDraft"] is True
    assert patched.json()["settings"]["draftRetentionDays"] == 14
    # 0 goes back to the default; leaving the key out changes nothing
    kept = await client.patch(
        settings_url(workspace, form), json={"purpose": "x"}, cookies=test_user_cookies
    )
    assert kept.json()["settings"]["draftRetentionDays"] == 14
    reset = await client.patch(
        settings_url(workspace, form),
        json={"draftRetentionDays": 0, "allowSaveDraft": False},
        cookies=test_user_cookies,
    )
    assert reset.json()["settings"]["draftRetentionDays"] is None
    assert reset.json()["settings"]["allowSaveDraft"] is False


@pytest.mark.parametrize("days", [-1, 91, 1000, 1.5, "7", True, [7]])
async def test_days_outside_the_bounds_are_refused(
    client, workspace, test_user_cookies, days
):
    form = await publish(workspace)
    refused = await client.patch(
        settings_url(workspace, form),
        json={"draftRetentionDays": days},
        cookies=test_user_cookies,
    )
    assert refused.status_code == 422, refused.text


async def test_only_someone_who_may_edit_the_form_changes_it(client, workspace):
    form = await publish(workspace)
    refused = await client.patch(
        settings_url(workspace, form),
        json={"allowSaveDraft": True},
        cookies=cookies(testUser1),
    )
    assert refused.status_code in (403, 404)
    assert (
        await client.patch(settings_url(workspace, form), json={"allowSaveDraft": True})
    ).status_code == 401


async def test_respondents_read_the_setting_and_the_days_with_the_form(
    client, workspace
):
    form = await drafting_form(workspace, draft_retention_days=21)
    read = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}?published=true",
        cookies=cookies(testUser1),
    )
    assert read.status_code == 200, read.text
    settings = read.json()["settings"]
    assert settings["allowSaveDraft"] is True and settings["draftRetentionDays"] == 21
    plain = await publish(workspace)
    read = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{plain.form_id}?published=true"
    )
    assert not read.json()["settings"].get("allowSaveDraft")


def test_the_ops_engine_sets_both_and_checks_the_days():
    ops = parse_ops(
        [
            {
                "op": "update_form_settings",
                "patch": {"allowSaveDraft": True, "draftRetentionDays": 30},
            },
            {"op": "update_form_settings", "patch": {"draftRetentionDays": 91}},
            {"op": "update_form_settings", "patch": {"draftRetentionDays": 0}},
            {"op": "update_form_settings", "patch": {}},
        ]
    )
    _, results = apply_form_ops(StandardForm(fields=[]), ops)
    assert [r.ok for r in results] == [True, False, True, False]
    assert "between 1 and 90" in results[1].message
    assert "allowSaveDraft" in results[3].message
    settings = WorkspaceFormSettings()
    assert apply_settings_ops(settings, ops[:1], results[:1]) is True
    assert (settings.allow_save_draft, settings.draft_retention_days) == (True, 30)
    apply_settings_ops(settings, ops[1:3], results[1:3])
    # the refused op changed nothing; 0 went back to the default
    assert (settings.allow_save_draft, settings.draft_retention_days) == (True, None)


def test_the_spec_carries_the_setting_in_its_trust_block():
    settings = WorkspaceFormSettings(allow_save_draft=True, draft_retention_days=45)
    spec = form_to_spec(StandardForm(fields=[], title="T"), settings)
    assert spec.trust.allow_save_draft is True and spec.trust.draft_retention_days == 45
    dumped = spec.model_dump(by_alias=True, exclude_none=True)["trust"]
    assert dumped["allowSaveDraft"] is True and dumped["draftRetentionDays"] == 45
    assert (
        form_to_spec(StandardForm(fields=[], title="T"), WorkspaceFormSettings()).trust
        is None
    )
    base = {"specVersion": "1", "pages": []}
    for days in (0, 91, -3):
        with pytest.raises(ValidationError):
            FormSpec.model_validate({**base, "trust": {"draftRetentionDays": days}})
    FormSpec.model_validate(
        {**base, "trust": {"allowSaveDraft": False, "draftRetentionDays": 90}}
    )
