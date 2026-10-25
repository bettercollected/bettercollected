"""GOOGLE_FORMS_IMPORT=on|readonly|off: what each mode allows.

``readonly`` refuses (403 ``google_forms_readonly``) every new import,
re-sync, account connection and Google Forms listing while imported forms and
their responses stay readable; ``off`` answers 410 ``google_forms_off`` and
never calls the Google Forms service, for anything.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from backend.app.container import container
from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.services.form_service import FormService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.config import settings
from backend.config.google_forms_settings import GoogleFormsSettings
from tests.app.controllers.data import testUser
from tests.app.controllers.test_workspace_forms import create_form_request_body

ROOT = "/api/v1"
GOOGLE_URL = "http://google-forms.invalid"


@pytest.fixture()
def mode(monkeypatch):
    def set_mode(value: str):
        monkeypatch.setattr(settings.google_forms, "IMPORT", value)

    return set_mode


@pytest.fixture()
async def google_provider_config():
    await container.form_provider_service().add_provider(
        FormProviderConfigDto(
            enabled=True,
            provider_name="google",
            provider_url=GOOGLE_URL,
            auth_callback_url=f"{GOOGLE_URL}/google/oauth/callback",
        )
    )


@pytest.fixture()
def user_details():
    """Reading a form asks the auth service for the importer's details."""
    with patch.object(
        FormService,
        "fetch_user_details",
        AsyncMock(return_value={"users_info": [{"_id": testUser.id}]}),
    ):
        yield


@pytest.fixture()
def proxied():
    """Every request the plugin proxy would forward to the Google service."""
    with patch.object(
        PluginProxyService, "pass_request", AsyncMock(return_value={"ok": True})
    ) as pass_request:
        yield pass_request


def _code(response):
    body = response.json()
    return body.get("code") if isinstance(body, dict) else None


PROXY_ROUTES = [
    ("GET", "/google/forms"),
    ("GET", "/google/forms/form-1?email=user@example.com"),
    ("GET", "/google/import/form-1"),
    ("GET", "/google/import"),
    ("GET", "/google/oauth/verify"),
]


class TestSettings:
    def test_the_default_is_on(self):
        assert GoogleFormsSettings.model_fields["IMPORT"].default == "on"

    def test_values_are_normalised(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_FORMS_IMPORT", " ReadOnly ")
        assert GoogleFormsSettings().IMPORT == "readonly"

    def test_an_unknown_value_refuses_to_start(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_FORMS_IMPORT", "maybe")
        with pytest.raises(ValidationError):
            GoogleFormsSettings()


class TestProxyRoutes:
    @pytest.mark.parametrize("method,path", PROXY_ROUTES)
    async def test_on_forwards_to_the_google_service(
        self,
        client: AsyncClient,
        test_user_cookies,
        google_provider_config,
        proxied,
        mode,
        method,
        path,
    ):
        mode("on")
        response = await client.request(method, ROOT + path, cookies=test_user_cookies)

        assert response.status_code == 200
        assert proxied.await_count == 1
        assert proxied.await_args.args[1].startswith(f"{GOOGLE_URL}/google/")

    @pytest.mark.parametrize("method,path", PROXY_ROUTES)
    @pytest.mark.parametrize(
        "value,status,code",
        [("readonly", 403, "google_forms_readonly"), ("off", 410, "google_forms_off")],
    )
    async def test_readonly_and_off_refuse_without_calling_it(
        self,
        client: AsyncClient,
        test_user_cookies,
        google_provider_config,
        proxied,
        mode,
        method,
        path,
        value,
        status,
        code,
    ):
        mode(value)
        response = await client.request(method, ROOT + path, cookies=test_user_cookies)

        assert response.status_code == status
        assert _code(response) == code
        assert response.json()["message"]
        proxied.assert_not_awaited()


class TestImport:
    async def test_on_imports(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        mock_aiohttp_post_request,
        mode,
    ):
        mode("on")
        with mock_aiohttp_post_request as convert:
            body = await create_form_request_body(workspace_form.form_id)
            response = await client.post(
                f"{ROOT}/workspaces/{workspace.id}/forms/import/google",
                cookies=test_user_cookies,
                json=body,
            )
        assert response.status_code == 200
        assert convert.await_count == 1

    @pytest.mark.parametrize(
        "value,status,code",
        [("readonly", 403, "google_forms_readonly"), ("off", 410, "google_forms_off")],
    )
    async def test_readonly_and_off_refuse_an_import_or_resync_but_keep_imported_data(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        mock_aiohttp_post_request,
        user_details,
        mode,
        value,
        status,
        code,
    ):
        import_url = f"{ROOT}/workspaces/{workspace.id}/forms/import/google"
        mode("on")
        with mock_aiohttp_post_request as convert:
            body = await create_form_request_body(workspace_form.form_id)
            imported = await client.post(import_url, cookies=test_user_cookies, json=body)
            assert imported.status_code == 200
            form_id = imported.json()["formId"]
            before = await client.get(
                f"{ROOT}/workspaces/{workspace.id}/forms/{form_id}/submissions",
                cookies=test_user_cookies,
            )
            assert before.status_code == 200 and before.json()["total"] >= 1

            mode(value)
            # the same form again is a re-sync: refused like a new import
            resync = await client.post(import_url, cookies=test_user_cookies, json=body)
            assert convert.await_count == 1

        assert resync.status_code == status
        assert _code(resync) == code
        # what was imported stays readable from our store
        form = await client.get(
            f"{ROOT}/workspaces/{workspace.id}/forms/{form_id}",
            cookies=test_user_cookies,
        )
        assert form.status_code == 200
        assert form.json()["title"] == imported.json()["title"]
        after = await client.get(
            f"{ROOT}/workspaces/{workspace.id}/forms/{form_id}/submissions",
            cookies=test_user_cookies,
        )
        assert after.status_code == 200
        assert after.json()["total"] == before.json()["total"]

    async def test_the_mode_is_checked_after_the_permission(
        self, client: AsyncClient, workspace, test_user_cookies_1, mode
    ):
        mode("readonly")
        response = await client.post(
            f"{ROOT}/workspaces/{workspace.id}/forms/import/google",
            cookies=test_user_cookies_1,
            json={"form": {"formId": "x"}, "response_data_owner": "x"},
        )
        assert response.status_code == 403
        assert _code(response) is None  # a non-member learns nothing more


class TestConnectingAnAccount:
    @pytest.fixture()
    def auth_http(self):
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value={"oauth_url": "https://google/oauth"})
        with patch.object(container.auth_service(), "http_client", http_client):
            yield http_client

    async def test_on_returns_the_oauth_url(
        self, client, test_user_cookies, google_provider_config, auth_http, mode
    ):
        mode("on")
        response = await client.get(
            f"{ROOT}/auth/google/oauth",
            cookies=test_user_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 307
        assert response.headers["location"] == "https://google/oauth"
        assert auth_http.get.await_count == 1

    @pytest.mark.parametrize(
        "value,status,code",
        [("readonly", 403, "google_forms_readonly"), ("off", 410, "google_forms_off")],
    )
    @pytest.mark.parametrize("path", ["/auth/google/oauth", "/auth/google/oauth/callback?state=s&code=c"])
    async def test_readonly_and_off_refuse(
        self,
        client,
        test_user_cookies,
        google_provider_config,
        auth_http,
        proxied,
        mode,
        value,
        status,
        code,
        path,
    ):
        mode(value)
        response = await client.get(ROOT + path, cookies=test_user_cookies)

        assert response.status_code == status
        assert _code(response) == code
        auth_http.get.assert_not_awaited()
        proxied.assert_not_awaited()


class TestProviders:
    async def test_on_and_readonly_list_google_with_its_mode(
        self, client, google_provider_config, mode
    ):
        for value in ("on", "readonly"):
            mode(value)
            response = await client.get(f"{ROOT}/providers")
            assert response.status_code == 200
            assert {"providerName": "google", "importMode": value} in response.json()

    async def test_off_does_not_list_google(self, client, google_provider_config, mode):
        mode("off")
        response = await client.get(f"{ROOT}/providers")

        assert response.status_code == 200
        assert "google" not in [p["providerName"] for p in response.json()]
        single = await client.get(f"{ROOT}/providers/google")
        assert single.status_code == 410
        assert _code(single) == "google_forms_off"


class TestSheets:
    """The Sheets action is not Google Forms work: it stays in readonly, and
    stops in off only because it still goes through the Google service."""

    @pytest.fixture()
    def sheets_http(self):
        provider = (
            container.integration_service().integration__provider_factory.google_integration_provider
        )
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value={"oauth_url": "https://google/oauth"})
        with patch.object(provider, "http_client", http_client):
            yield http_client

    URL = f"{ROOT}/integration/{FormIntegrationType.GOOGLE_SHEET.value}/oauth"

    @pytest.mark.parametrize("value", ["on", "readonly"])
    async def test_on_and_readonly_connect_sheets(
        self, client, test_user_cookies, google_provider_config, sheets_http, mode, value
    ):
        mode(value)
        response = await client.get(self.URL, cookies=test_user_cookies)

        assert response.status_code == 200
        assert sheets_http.get.await_args.args[0].startswith(GOOGLE_URL)

    async def test_off_never_calls_the_google_service(
        self, client, test_user_cookies, google_provider_config, sheets_http, mode
    ):
        mode("off")
        response = await client.get(self.URL, cookies=test_user_cookies)

        assert response.status_code == 410
        assert _code(response) == "google_forms_off"
        sheets_http.get.assert_not_awaited()


class TestAccountDeletion:
    @pytest.fixture()
    def aiohttp_delete(self):
        session = MagicMock()
        session.delete = AsyncMock(return_value=MagicMock(status=200))
        with patch(
            "backend.app.services.auth_service.AiohttpClient.get_aiohttp_client",
            return_value=session,
        ):
            yield session.delete

    @pytest.mark.parametrize("value", ["on", "readonly"])
    async def test_on_and_readonly_delete_the_stored_credentials(
        self, google_provider_config, aiohttp_delete, mode, value
    ):
        mode(value)
        await container.auth_service().delete_credentials_from_integrations(testUser)

        assert aiohttp_delete.await_count == 1
        assert aiohttp_delete.await_args.args[0] == (
            f"{GOOGLE_URL}/google/oauth/credentials"
        )

    async def test_off_skips_the_google_service_and_queues_a_purge(
        self, google_provider_config, aiohttp_delete, mode
    ):
        mode("off")
        with patch.object(
            container.temporal_service(),
            "queue_credential_purge",
            AsyncMock(return_value="queued"),
        ) as queue:
            await container.auth_service().delete_credentials_from_integrations(
                testUser
            )

        aiohttp_delete.assert_not_awaited()
        assert queue.await_count == 1
