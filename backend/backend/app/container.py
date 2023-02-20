import os
from pathlib import Path

from dependency_injector import containers, providers
from motor.motor_asyncio import AsyncIOMotorClient

from backend.app.core.form_plugin_config import FormProvidersConfig
from backend.app.services.auth_service import AuthService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.config import settings
from common.services.http_client import HttpClient

current_path = Path(os.path.abspath(os.path.dirname(__file__))).absolute()


class AppContainer(containers.DeclarativeContainer):
    forms_config = providers.Configuration(
        json_files=[current_path.joinpath("core/plugin.json")], strict=True
    )

    form_providers: FormProvidersConfig = providers.Singleton(
        FormProvidersConfig, form_providers=forms_config.form_providers
    )

    http_client: HttpClient = providers.Singleton(HttpClient)

    database_client: AsyncIOMotorClient = providers.Singleton(
        AsyncIOMotorClient, settings.mongo_settings.URI
    )

    plugin_proxy_service: PluginProxyService = providers.Singleton(
        PluginProxyService,
        http_client=http_client
    )

    auth_service: AuthService = providers.Singleton(
        AuthService,
        http_client=http_client,
        plugin_proxy_service=plugin_proxy_service,
        form_providers=form_providers
    )


container = AppContainer()
print("Debug")
