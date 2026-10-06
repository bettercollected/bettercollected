"""The settings-patch rules hold on every path that stores them: the
retention period (a date must be in the future) and the privacy policy link
(http(s) only) on form create and update, the settings patch and AI chat."""

import datetime as dt
import json

import pytest
from httpx import AsyncClient

from common.models.standard_form import StandardForm, StandardFormSettings

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.services.ai.ops import FormOps, apply_form_ops
from backend.app.services.policy_url import checked_policy_url
from backend.app.services.retention import checked_retention
from tests.app.controllers.data import testUser

TODAY = dt.date.today()
PAST = (TODAY - dt.timedelta(days=1)).isoformat()
FUTURE = (TODAY + dt.timedelta(days=30)).isoformat()


def _form(**settings):
    return StandardForm(
        title="Form",
        fields=[],
        settings=StandardFormSettings(**settings) if settings else None,
    )


async def _stored(workspace, form_id):
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form_id)
        )
    )
    settings = workspace_form.settings
    kind = settings.response_expiration_type
    return getattr(kind, "value", kind), settings.response_expiration


# --- the shared rules ----------------------------------------------------------


@pytest.mark.parametrize(
    "kind,value,expected",
    [
        (None, None, (None, None)),
        (None, "", (None, None)),
        ("", "", (None, None)),
        ("forever", "30", ("forever", None)),
        ("days", " 030 ", ("days", "30")),
        ("date", FUTURE, ("date", FUTURE)),
    ],
)
def test_usable_retention_is_normalised(kind, value, expected):
    stored_kind, stored_value = checked_retention(kind, value, TODAY)
    assert (getattr(stored_kind, "value", stored_kind), stored_value) == expected


@pytest.mark.parametrize(
    "kind,value",
    [
        (None, "30"),
        ("days", "0"),
        ("days", "3651"),
        ("days", "soon"),
        ("date", PAST),
        ("date", TODAY.isoformat()),
        ("date", "2027-02-30"),
        ("weeks", "3"),
    ],
)
def test_unusable_retention_is_refused(kind, value):
    with pytest.raises(ValueError):
        checked_retention(kind, value, TODAY)


@pytest.mark.parametrize(
    "url",
    ["https://example.org/privacy", "http://example.org", "HTTPS://Example.org/p?q=1"],
)
def test_http_policy_links_are_kept(url):
    assert checked_policy_url(f"  {url} ") == url


def test_a_blank_policy_link_clears_it():
    assert checked_policy_url("   ") == ""
    assert checked_policy_url(None) is None


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox",
        "ftp://example.org/policy",
        "//example.org/privacy",
        "/privacy",
        "example.org/privacy",
        "https://",
        "https://exa mple.org",
        "https://example.org/\nprivacy",
    ],
)
def test_other_policy_links_are_refused(url):
    with pytest.raises(ValueError):
        checked_policy_url(url)


@pytest.mark.parametrize(
    "body",
    [
        {"privacyPolicyUrl": "javascript:alert(1)"},
        {"privacyPolicyUrl": "ftp://example.org"},
    ],
)
def test_the_settings_patch_refuses_other_policy_links(body):
    with pytest.raises(ValueError):
        SettingsPatchDto(**body)


async def test_settings_endpoint_answers_422_for_a_script_link(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    url = f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/settings"
    refused = await client.patch(
        url, json={"privacyPolicyUrl": "javascript:alert(1)"}, cookies=test_user_cookies
    )
    assert refused.status_code == 422
    accepted = await client.patch(
        url,
        json={"privacyPolicyUrl": "https://example.org/privacy"},
        cookies=test_user_cookies,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["settings"]["privacyPolicyUrl"] == (
        "https://example.org/privacy"
    )


# --- form create -------------------------------------------------------------


async def test_create_refuses_a_past_retention_date(workspace):
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().create_form(
            workspace.id,
            _form(response_expiration_type="date", response_expiration=PAST),
            testUser,
        )
    assert raised.value.status_code == 422


async def test_create_refuses_a_script_policy_link(workspace):
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().create_form(
            workspace.id, _form(privacy_policy_url="javascript:alert(1)"), testUser
        )
    assert raised.value.status_code == 422


async def test_create_stores_a_usable_retention_normalised(workspace):
    form = await container.workspace_form_service().create_form(
        workspace.id,
        _form(response_expiration_type="days", response_expiration="045"),
        testUser,
    )
    assert await _stored(workspace, form.form_id) == ("days", "45")


async def test_create_without_settings_keeps_answers_until_deleted(workspace):
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(), testUser
    )
    assert await _stored(workspace, form.form_id) == (None, None)


async def test_a_copy_drops_a_passed_date_instead_of_failing(workspace):
    form = await container.workspace_form_service().create_form(
        workspace.id,
        _form(
            response_expiration_type="date",
            response_expiration=PAST,
            privacy_policy_url="javascript:alert(1)",
        ),
        testUser,
        drop_unusable_settings=True,
    )
    # No period (kept until deleted) and no link, rather than no form.
    assert await _stored(workspace, form.form_id) == (None, None)
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form.form_id)
        )
    )
    assert not workspace_form.settings.privacy_policy_url


async def test_create_endpoint_answers_422_for_a_past_date(
    client: AsyncClient, workspace, test_user_cookies
):
    body = {
        "title": "Form",
        "fields": [],
        "settings": {"responseExpirationType": "date", "responseExpiration": PAST},
    }
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms",
        data={"form_body": json.dumps(body)},
        cookies=test_user_cookies,
    )
    assert response.status_code == 422


# --- form update -------------------------------------------------------------


async def _form_with(workspace, **settings):
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(**settings), testUser
    )
    return form.form_id


async def _update(workspace, form_id, **settings):
    return await container.workspace_form_service().update_form(
        workspace.id, form_id, _form(**settings), testUser
    )


async def test_update_refuses_a_past_retention_date(workspace):
    form_id = await _form_with(workspace)
    with pytest.raises(HTTPException) as raised:
        await _update(
            workspace,
            form_id,
            response_expiration_type="date",
            response_expiration=PAST,
        )
    assert raised.value.status_code == 422
    assert await _stored(workspace, form_id) == (None, None)


async def test_update_refuses_days_out_of_range(workspace):
    form_id = await _form_with(
        workspace, response_expiration_type="days", response_expiration="30"
    )
    with pytest.raises(HTTPException):
        await _update(workspace, form_id, response_expiration="0")
    assert await _stored(workspace, form_id) == ("days", "30")


async def test_update_stores_a_usable_retention(workspace):
    form_id = await _form_with(workspace)
    await _update(
        workspace, form_id, response_expiration_type="date", response_expiration=FUTURE
    )
    assert await _stored(workspace, form_id) == ("date", FUTURE)
    await _update(workspace, form_id, response_expiration_type="forever")
    assert await _stored(workspace, form_id) == ("forever", None)


async def test_update_sending_back_a_since_passed_date_still_saves(workspace):
    """A form whose end date has passed since it was set can still be
    saved with its settings unchanged: only a change is checked."""
    form_id = await _form_with(
        workspace, response_expiration_type="date", response_expiration=FUTURE
    )
    repo = container.workspace_form_repo()
    workspace_form = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form_id)
    )
    workspace_form.settings.response_expiration = PAST
    await repo.save(workspace_form)

    await _update(
        workspace, form_id, response_expiration_type="date", response_expiration=PAST
    )
    assert await _stored(workspace, form_id) == ("date", PAST)


async def test_update_refuses_a_script_policy_link(workspace):
    form_id = await _form_with(workspace, privacy_policy_url="https://example.org/p")
    with pytest.raises(HTTPException) as raised:
        await _update(workspace, form_id, privacy_policy_url="javascript:alert(1)")
    assert raised.value.status_code == 422


# --- AI chat -----------------------------------------------------------------


def test_ai_settings_op_refuses_a_script_policy_link():
    form = StandardForm(title="Form", fields=[])
    _, results = apply_form_ops(
        form,
        FormOps.model_validate(
            {
                "ops": [
                    {
                        "op": "update_form_settings",
                        "patch": {"privacyPolicyUrl": "javascript:alert(1)"},
                    }
                ]
            }
        ).ops,
    )
    assert not results[0].ok
    _, results = apply_form_ops(
        form,
        FormOps.model_validate(
            {
                "ops": [
                    {
                        "op": "update_form_settings",
                        "patch": {"privacyPolicyUrl": "https://example.org/p"},
                    }
                ]
            }
        ).ops,
    )
    assert results[0].ok
