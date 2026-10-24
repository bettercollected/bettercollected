"""The Typeform integration is removed: no login or import route takes it, and
a stored provider row for it is never offered or called (account deletion
would otherwise call a service that no longer runs). Forms and responses
imported from Typeform keep their provider text and stay readable."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from common.enums.form_provider import FormProvider
from common.enums.login_provider import LoginProvider
from common.models.standard_form import StandardForm


def _row(name: str, enabled: bool = True) -> FormProviderConfigDto:
    return FormProviderConfigDto(
        enabled=enabled,
        provider_name=name,
        provider_url=f"http://integrations-{name}:8000/api/v1",
        auth_callback_url=f"http://integrations-{name}:8000/api/v1/{name}/oauth/callback",
        type="oauth2",
    )


def _service(*rows) -> FormPluginProviderService:
    return FormPluginProviderService(SimpleNamespace(list=AsyncMock(return_value=list(rows))))


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
    assert [p.provider_name for p in await service.get_providers(get_all=True)] == ["google"]


def _path_refused(response) -> bool:
    return response.status_code == 422 and response.json()["detail"][0]["loc"][0] == "path"


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
