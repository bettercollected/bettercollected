import os
from pathlib import Path

from dependency_injector import containers, providers
from motor.motor_asyncio import AsyncIOMotorClient

from backend.app.core.form_plugin_config import FormProvidersConfig
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.services.auth_service import AuthService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.form_service import FormService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.workspace_service import WorkspaceService
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.config import settings
from common.services.http_client import HttpClient

current_path = Path(os.path.abspath(os.path.dirname(__file__))).absolute()


class AppContainer(containers.DeclarativeContainer):
    http_client: HttpClient = providers.Singleton(HttpClient)

    database_client: AsyncIOMotorClient = providers.Singleton(
        AsyncIOMotorClient, settings.mongo_settings.URI
    )

    # Repositories
    workspace_user_repo: WorkspaceUserRepository = providers.Singleton(
        WorkspaceUserRepository
    )

    workspace_repo: WorkspaceRepository = providers.Singleton(WorkspaceRepository)

    form_repo: FormRepository = providers.Singleton(FormRepository)
    form_response_repo: FormResponseRepository = providers.Singleton(
        FormResponseRepository
    )
    workspace_form_repo: WorkspaceFormRepository = providers.Singleton(
        WorkspaceFormRepository
    )

    form_provider_repo: FormPluginProviderRepository = providers.Singleton(
        FormPluginProviderRepository
    )

    # Services
    aws_service: AWSS3Service = providers.Singleton(
        AWSS3Service,
        settings.aws_settings.access_key_id,
        settings.aws_settings.secret_access_key,
    )

    form_provider_service: FormPluginProviderService = providers.Singleton(
        FormPluginProviderService, form_provider_repo=form_provider_repo
    )

    plugin_proxy_service: PluginProxyService = providers.Singleton(
        PluginProxyService, http_client=http_client
    )

    auth_service: AuthService = providers.Singleton(
        AuthService,
        http_client=http_client,
        plugin_proxy_service=plugin_proxy_service,
        form_provider_service=form_provider_service,
    )

    workspace_service: WorkspaceService = providers.Singleton(
        WorkspaceService,
        workspace_repo=workspace_repo,
        aws_service=aws_service,
        workspace_user_repo=workspace_user_repo,
    )

    form_service: FormService = providers.Singleton(
        FormService,
        workspace_user_repo=workspace_user_repo,
        form_repo=form_repo,
        workspace_form_repo=workspace_form_repo,
    )

    form_response_service: FormResponseService = providers.Singleton(
        FormResponseService,
        form_response_repo=form_response_repo,
        workspace_form_repo=workspace_form_repo,
        workspace_user_repo=workspace_user_repo,
    )


container = AppContainer()
