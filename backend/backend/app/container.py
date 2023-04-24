import os
from pathlib import Path

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schedulers.form_schedular import FormSchedular
from backend.app.services.auth_service import AuthService
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.form_import_service import FormImportService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.form_service import FormService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.stripe_service import StripeService
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_members_service import WorkspaceMembersService
from backend.app.services.workspace_service import WorkspaceService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings

from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService

from dependency_injector import containers, providers

from motor.motor_asyncio import AsyncIOMotorClient

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
        settings.aws_settings.ACCESS_KEY_ID,
        settings.aws_settings.SECRET_ACCESS_KEY,
    )

    jwt_service: JwtService = providers.Singleton(
        JwtService, settings.auth_settings.JWT_SECRET
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
        jwt_service=jwt_service,
    )

    stripe_service: StripeService = providers.Singleton(
        StripeService,
        http_client=http_client,
        plugin_proxy_service=plugin_proxy_service,
        form_provider_service=form_provider_service,
        jwt_service=jwt_service,
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

    workspace_user_service: WorkspaceUserService = providers.Singleton(
        WorkspaceUserService, workspace_user_repository=workspace_user_repo
    )

    job_store = providers.Singleton(MongoDBJobStore, host=settings.mongo_settings.URI)

    job_stores = providers.Dict(default=job_store)

    # executors = providers.Dict(
    #     default=ThreadPoolExecutor(100)
    # )

    schedular = providers.Singleton(
        AsyncIOScheduler,
        jobstores=job_stores,
    )

    form_import_service: FormImportService = providers.Singleton(
        FormImportService, form_service=form_service
    )

    form_schedular = providers.Singleton(
        FormSchedular,
        form_provider_service=form_provider_service,
        form_import_service=form_import_service,
        jwt_service=jwt_service,
    )

    workspace_form_service: WorkspaceFormService = providers.Singleton(
        WorkspaceFormService,
        form_provider_service=form_provider_service,
        plugin_proxy_service=plugin_proxy_service,
        workspace_user_service=workspace_user_service,
        form_service=form_service,
        workspace_form_repository=workspace_form_repo,
        form_schedular=form_schedular,
        form_import_service=form_import_service,
        schedular=schedular,
        form_response_service=form_response_service,
    )

    workspace_service: WorkspaceService = providers.Singleton(
        WorkspaceService,
        http_client=http_client,
        workspace_repo=workspace_repo,
        aws_service=aws_service,
        workspace_user_service=workspace_user_service,
        workspace_form_service=workspace_form_service,
        form_response_service=form_response_service,
    )

    workspace_invitation_repo: WorkspaceInvitationRepo = providers.Singleton(
        WorkspaceInvitationRepo
    )

    workspace_members_service: WorkspaceMembersService = providers.Singleton(
        WorkspaceMembersService,
        workspace_user_service=workspace_user_service,
        workspace_invitation_repo=workspace_invitation_repo,
        http_client=http_client,
    )


container = AppContainer()
