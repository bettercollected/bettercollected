import os
from pathlib import Path

from concurrent.futures.thread import ThreadPoolExecutor

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from common.configs.crypto import Crypto
from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService
from dependency_injector import containers, providers
from motor.motor_asyncio import AsyncIOMotorClient

from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.coupon_repository import CouponRepository
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.media_library_repository import MediaLibraryRepository
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.repositories.template import FormTemplateRepository
from backend.app.repositories.user_feedback import UserFeedbackRepo
from backend.app.repositories.user_tags_repository import UserTagsRepository
from backend.app.repositories.workspace_consent_repo import WorkspaceConsentRepo
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_responders_repository import (
    WorkspaceRespondersRepository,
)
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schedulers.form_schedular import FormSchedular
from backend.app.services.actions_service import ActionService
from backend.app.services.auth_service import AuthService
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.coupon_service import CouponService
from backend.app.services.feedback_service import UserFeedbackService
from backend.app.services.form_import_service import FormImportService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.form_service import FormService
from backend.app.services.media_library_service import MediaLibraryService
from backend.app.services.openai_service import OpenAIService
from backend.app.services.integration_action_service import IntegrationActionService
from backend.app.services.integration_provider_factory import IntegrationProviderFactory
from backend.app.services.integration_service import IntegrationService
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.price_suggestion import PriceSuggestionService
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.stripe_service import StripeService
from backend.app.services.template_service import FormTemplateService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.user_tags_service import UserTagsService
from backend.app.services.workspace_consent_service import WorkspaceConsentService
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_members_service import WorkspaceMembersService
from backend.app.services.workspace_responders_service import WorkspaceRespondersService
from backend.app.services.workspace_service import WorkspaceService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.services.umami_client import UmamiClient
from backend.app.services.analytics_service import AnalyticsService

from backend.app.services.form_actions_service import FormActionsService
from backend.config import settings

current_path = Path(os.path.abspath(os.path.dirname(__file__))).absolute()


class AppContainer(containers.DeclarativeContainer):
    http_client: HttpClient = providers.Singleton(HttpClient)

    database_client: AsyncIOMotorClient = providers.Singleton(
        AsyncIOMotorClient, settings.mongo_settings.URI
    )

    user_tags_repo = providers.Singleton(UserTagsRepository)
    user_tags_service = providers.Singleton(
        UserTagsService, user_tags_repo=user_tags_repo
    )
    crypto = providers.Singleton(Crypto, settings.auth_settings.AES_HEX_KEY)

    # Repositories

    coupon_repository: CouponRepository = providers.Singleton(CouponRepository)
    workspace_user_repo: WorkspaceUserRepository = providers.Singleton(
        WorkspaceUserRepository
    )
    workspace_repo: WorkspaceRepository = providers.Singleton(WorkspaceRepository)

    form_repo: FormRepository = providers.Singleton(FormRepository)
    form_response_repo: FormResponseRepository = providers.Singleton(
        FormResponseRepository, crypto=crypto
    )
    workspace_form_repo: WorkspaceFormRepository = providers.Singleton(
        WorkspaceFormRepository
    )

    form_provider_repo: FormPluginProviderRepository = providers.Singleton(
        FormPluginProviderRepository
    )

    responder_groups_repository = providers.Singleton(ResponderGroupsRepository)

    action_repository = providers.Singleton(ActionRepository, crypto=crypto)

    integration_action_service: IntegrationActionService = providers.Singleton(
        IntegrationActionService
    )

    temporal_service = providers.Singleton(
        TemporalService,
        server_uri=settings.temporal_settings.server_uri,
        namespace=settings.temporal_settings.namespace,
        crypto=crypto,
    )

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

    integration_provider: IntegrationProviderFactory = providers.Singleton(
        IntegrationProviderFactory,
        form_provider_service=form_provider_service,
        crypto=crypto,
        http_client=http_client,
        integration_action_service=integration_action_service,
    )

    form_service: FormService = providers.Singleton(
        FormService,
        workspace_user_repo=workspace_user_repo,
        form_repo=form_repo,
        workspace_form_repo=workspace_form_repo,
        user_tags_service=user_tags_service,
        crypto=crypto,
        http_client=http_client,
        integration_provider=integration_provider,
    )

    form_response_service: FormResponseService = providers.Singleton(
        FormResponseService,
        form_response_repo=form_response_repo,
        workspace_form_repo=workspace_form_repo,
        workspace_user_repo=workspace_user_repo,
        aws_service=aws_service,
    )

    workspace_user_service: WorkspaceUserService = providers.Singleton(
        WorkspaceUserService, workspace_user_repository=workspace_user_repo
    )

    job_store = providers.Singleton(MongoDBJobStore, host=settings.mongo_settings.URI)

    job_stores = providers.Dict(default=job_store)

    schedular = providers.Singleton(
        AsyncIOScheduler,
        jobstores=job_stores,
    )

    form_import_service: FormImportService = providers.Singleton(
        FormImportService, form_service=form_service, workspace_repo=workspace_repo
    )

    form_schedular = providers.Singleton(
        FormSchedular,
        form_provider_service=form_provider_service,
        form_import_service=form_import_service,
        jwt_service=jwt_service,
        temporal_service=temporal_service,
        form_response_service=form_response_service,
    )

    responder_groups_service = providers.Singleton(
        ResponderGroupsService,
        responder_groups_repo=responder_groups_repository,
        workspace_user_service=workspace_user_service,
        form_service=form_service,
    )

    action_service = providers.Singleton(
        ActionService,
        action_repository=action_repository,
        temporal_service=temporal_service,
        workspace_user_service=workspace_user_service,
        http_client=http_client,
        form_provider_service=form_provider_service,
        form_response_service=form_response_service,
        workspace_repo=workspace_repo,
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
        responder_groups_service=responder_groups_service,
        user_tags_service=user_tags_service,
        temporal_service=temporal_service,
        aws_service=aws_service,
        action_service=action_service,
        crypto=crypto,
    )

    workspace_service: WorkspaceService = providers.Singleton(
        WorkspaceService,
        http_client=http_client,
        workspace_repo=workspace_repo,
        aws_service=aws_service,
        workspace_user_service=workspace_user_service,
        workspace_form_service=workspace_form_service,
        form_response_service=form_response_service,
        responder_groups_service=responder_groups_service,
        user_tags_service=user_tags_service,
    )

    openai_service: OpenAIService = providers.Singleton(
        OpenAIService,
        workspace_service=workspace_service,
        workspace_form_service=workspace_form_service,
    )

    auth_service: AuthService = providers.Singleton(
        AuthService,
        http_client=http_client,
        plugin_proxy_service=plugin_proxy_service,
        form_provider_service=form_provider_service,
        jwt_service=jwt_service,
        workspace_service=workspace_service,
        temporal_service=temporal_service,
        crypto=crypto,
        user_tags_service=user_tags_service,
    )

    workspace_invitation_repo: WorkspaceInvitationRepo = providers.Singleton(
        WorkspaceInvitationRepo
    )

    workspace_members_service: WorkspaceMembersService = providers.Singleton(
        WorkspaceMembersService,
        workspace_user_service=workspace_user_service,
        workspace_invitation_repo=workspace_invitation_repo,
        http_client=http_client,
        workspace_form_service=workspace_form_service,
    )

    stripe_service: StripeService = providers.Singleton(
        StripeService,
        http_client=http_client,
        plugin_proxy_service=plugin_proxy_service,
        form_provider_service=form_provider_service,
        jwt_service=jwt_service,
        workspace_service=workspace_service,
    )

    workspace_responders_repo = providers.Singleton(WorkspaceRespondersRepository)
    workspace_responders_service = providers.Singleton(
        WorkspaceRespondersService,
        workspace_responders_repo=workspace_responders_repo,
        workspace_user_service=workspace_user_service,
        form_response_service=form_response_service,
    )
    workspace_consent_repo = providers.Singleton(WorkspaceConsentRepo)

    workspace_consent_service = providers.Singleton(
        WorkspaceConsentService,
        workspace_user_service=workspace_user_service,
        workspace_consent_repo=workspace_consent_repo,
    )

    form_template_repo = providers.Singleton(FormTemplateRepository)

    form_template_service = providers.Singleton(
        FormTemplateService,
        workspace_user_service=workspace_user_service,
        form_template_repo=form_template_repo,
        workspace_form_service=workspace_form_service,
        aws_service=aws_service,
        temporal_service=temporal_service,
    )

    user_feedback_repo = providers.Singleton(UserFeedbackRepo)

    user_feedback_service = providers.Singleton(
        UserFeedbackService, user_feedback_repo=user_feedback_repo
    )

    coupon_service = providers.Singleton(
        CouponService,
        coupon_repository=coupon_repository,
        auth_service=auth_service,
        workspace_service=workspace_service,
    )

    price_suggestion_service = providers.Singleton(
        PriceSuggestionService,
        auth_service=auth_service,
        workspace_service=workspace_service,
    )

    media_library_repo = providers.Singleton(MediaLibraryRepository)

    media_library_service = providers.Singleton(
        MediaLibraryService,
        media_library_repo=media_library_repo,
        aws_service=aws_service,
    )

    umami_client: UmamiClient = providers.Singleton(UmamiClient)

    analytics_service: AnalyticsService = providers.Singleton(
        AnalyticsService,
        workspace_user_service=workspace_user_service,
    )

    integration_service: IntegrationService = providers.Singleton(
        IntegrationService,
        form_provider_service=form_provider_service,
        crypto=crypto,
        http_client=http_client,
        integration_action_service=integration_action_service,
    )

    form_actions_service: FormActionsService = providers.Singleton(
        FormActionsService, form_repo=form_repo
    )


container = AppContainer()
