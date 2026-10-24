"""The Typeform integration is removed: no login or import route takes it, and
a stored provider row for it is never offered or called (account deletion
would otherwise call a service that no longer runs). Forms and responses
imported from Typeform keep their provider text and stay readable."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.plugin_proxy_service import PluginProxyService
from common.enums.form_provider import FormProvider
from common.enums.login_provider import LoginProvider
from common.models.standard_form import StandardForm

from tests.app.controllers.data import formData, testUser


def _row(name: str, enabled: bool = True) -> FormProviderConfigDto:
    return FormProviderConfigDto(
        enabled=enabled,
        provider_name=name,
        provider_url=f"http://integrations-{name}:8000/api/v1",
        auth_callback_url=f"http://integrations-{name}:8000/api/v1/{name}/oauth/callback",
        type="oauth2",
    )


def _service(*rows) -> FormPluginProviderService:
    return FormPluginProviderService(
        SimpleNamespace(list=AsyncMock(return_value=list(rows)))
    )


def test_typeform_is_neither_a_login_nor_a_form_provider():
    assert [p.value for p in LoginProvider] == ["google"]
    assert FormProvider.list_providers() == ["google"]
    with pytest.raises(ValueError):
        LoginProvider("typeform")
    with pytest.raises(ValueError):
        FormProvider("typeform")


async def test_a_stored_typeform_row_is_not_offered_or_used_for_deletion():
    service = _service(_row("typeform"), _row("google"))
    assert await service.get_providers() == [{"provider_name": "google"}]
    # account deletion walks get_all=True and calls each enabled provider
    assert [p.provider_name for p in await service.get_providers(get_all=True)] == [
        "google"
    ]


def _path_refused(response) -> bool:
    return (
        response.status_code == 422 and response.json()["detail"][0]["loc"][0] == "path"
    )


async def test_the_login_and_import_routes_refuse_typeform(client):
    # sign-in: the provider in the path is not a login provider
    for path in ("/auth/typeform/basic", "/auth/typeform/basic/callback"):
        assert _path_refused(await client.get(f"/api/v1{path}")), path
    # import and proxy routes: refused (signed out, before the provider is even read)
    for path in ("/auth/typeform/oauth", "/typeform/forms"):
        response = await client.get(f"/api/v1{path}")
        assert response.status_code == 401 or _path_refused(response), path


def test_an_imported_typeform_form_keeps_its_provider():
    form = StandardForm.model_validate(
        {"form_id": "tf-1", "title": "Imported", "settings": {"provider": "typeform"}}
    )
    assert form.settings.provider == "typeform"


async def test_a_stored_typeform_row_is_never_read_for_a_url():
    # get_provider_if_enabled/get_provider_url feed the proxy, which forwards the
    # user's cookies and headers: an unlisted provider is refused before the row
    # is even read, whatever is stored for it
    repo = SimpleNamespace(
        get=AsyncMock(return_value=_row("typeform")),
        get_provider_url=AsyncMock(return_value=_row("typeform")),
    )
    service = FormPluginProviderService(repo)
    for call in (service.get_provider_if_enabled, service.get_provider_url):
        with pytest.raises(HTTPException) as refused:
            await call("typeform")
        assert refused.value.status_code == 404
    repo.get.assert_not_awaited()
    repo.get_provider_url.assert_not_awaited()


async def test_the_oauth_callback_refuses_typeform_and_forwards_nothing(
    client, test_user_cookies, monkeypatch
):
    forwarded = AsyncMock(return_value={})
    monkeypatch.setattr(PluginProxyService, "pass_request", forwarded)
    response = await client.get(
        "/api/v1/auth/typeform/oauth/callback",
        params={"state": "x", "code": "y"},
        cookies=test_user_cookies,
    )
    assert _path_refused(response)
    forwarded.assert_not_awaited()


async def test_a_stored_typeform_form_opens_and_deletes_end_to_end(
    client, workspace, test_user_cookies, mock_aiohttp_get_request
):
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**formData), testUser
    )
    # stored as an import from Typeform leaves it (create_form makes it native)
    stored = await container.form_repo().get_form_document_by_id(form.form_id)
    stored.settings.provider = "typeform"
    await container.form_repo().save_form(stored)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    link.settings.provider = "typeform"
    await container.workspace_form_repo().save(link)
    url = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}"
    with mock_aiohttp_get_request:
        opened = await client.get(url, cookies=test_user_cookies)
    assert opened.status_code == 200, opened.text
    assert opened.json()["settings"]["provider"] == "typeform"
    deleted = await client.delete(url, cookies=test_user_cookies)
    assert deleted.status_code == 200, deleted.text
