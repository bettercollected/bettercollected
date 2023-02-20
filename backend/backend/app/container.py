import os
from pathlib import Path

from dependency_injector import containers, providers
from motor.motor_asyncio import AsyncIOMotorClient

from backend.app.core.form_plugin_config import FormPluginConfig
from backend.config import settings
from common.services.http_client import HttpClient

current_path = Path(os.path.abspath(os.path.dirname(__file__))).absolute()


class AppContainer(containers.DeclarativeContainer):
    forms_config: FormPluginConfig = providers.Configuration(
        json_files=[current_path.joinpath("core/plugin.json")],
        strict=True)

    enabled_forms = providers.Singleton(
        FormPluginConfig,
        form_providers=forms_config.form_providers
    )

    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(
        HttpClient
    )

    database_client: AsyncIOMotorClient = providers.Singleton(
        AsyncIOMotorClient,
        settings.mongo_settings.URI
    )


container = AppContainer()
print("Debug")
