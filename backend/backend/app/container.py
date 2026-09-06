import os
from pathlib import Path

from concurrent.futures.thread import ThreadPoolExecutor

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from common.configs.crypto import Crypto
from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService
from dependency_injector import containers, providers
from pymongo import AsyncMongoClient

from backend.app.repositories.ai_preference_memory_repository import (
    AIPreferenceMemoryRepository,
)
from common.db import DatabaseSettings, load_flags
from common.db.routing import RoutingRepository

from backend.db.outbox import OutboxRecorder
from backend.db.groups import MONGO_JOINS
from backend.db.session import build_engine, build_sessionmaker, postgres_repository
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresFormTemplateRepository,
    PostgresMediaLibraryRepository,
    PostgresWorkspaceConsentRepo,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.postgres.identity import (
    PostgresBlacklistedRefreshTokenRepository,
    PostgresUserTagsRepository,
    PostgresWorkspaceAPIKeyRepository,
    PostgresWorkspaceInvitationRepo,
    PostgresWorkspaceRepository,
    PostgresWorkspaceUserRepository,
)
from backend.app.repositories.postgres.refdata import (
    PostgresAllowedOriginsRepository,
    PostgresCouponRepository,
    PostgresFormPluginProviderRepository,
    PostgresUserFeedbackRepo,
)

from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.form_ai_insight_repository import FormAIInsightRepository
from backend.app.repositories.form_ai_session_repository import FormAISessionRepository
from backend.app.repositories.workspace_ai_profile_repository import (
    WorkspaceAIProfileRepository,
)
from backend.app.repositories.workspace_api_key_repository import (
    WorkspaceAPIKeyRepository,
)
from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.blacklisted_refresh_token_repository import (
    BlacklistedRefreshTokenRepository,
)
from backend.app.repositories.coupon_repository import CouponRepository
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.flow_event_repository import FlowEventRepository
from backend.app.repositories.media_library_repository import MediaLibraryRepository
from backend.app.repositories.mcp_audit_log_repository import McpAuditLogRepository
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
from backend.app.services.ai.api_keys import APIKeyService
from backend.app.services.ai.chat import FormAIChatService
from backend.app.services.ai.memory import AIMemoryService
from backend.app.services.ai.profile import AIProfileService
from backend.app.services.ai.insights import FormAIInsightsService
from backend.app.services.ai.review import FormAIReviewService
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
from backend.app.middlewares.dynamic_cors_middleware import DynamicCORSMiddleware
from backend.config import settings

current_path = Path(os.path.abspath(os.path.dirname(__file__))).absolute()


class AppContainer(containers.DeclarativeContainer):
    http_client: HttpClient = providers.Singleton(HttpClient)

    database_client: AsyncMongoClient = providers.Object(None)
    # Mongo/Postgres switching (plans/postgres-consolidation.md D5): read once at boot,
    # validated; a bad combination refuses to start.
    flags = providers.Singleton(load_flags, mongo_joins=MONGO_JOINS)
    # Postgres: engine and sessions exist only when DATABASE_URL is set; the
    # routing layer treats the store as absent otherwise. Mirror-write failures
    # land in the primary store's outbox (backend/db/outbox.py).
    db_settings = providers.Singleton(DatabaseSettings.from_env)
    pg_engine = providers.Singleton(build_engine, db_settings)
    pg_sessionmaker = providers.Singleton(build_sessionmaker, pg_engine)
    outbox_recorder = providers.Singleton(OutboxRecorder, pg_sessionmaker)
    mirror_timeout_s = providers.Callable(
        lambda s: s.mirror_timeout_ms / 1000, db_settings
    )

    user_tags_repo = providers.Singleton(
        RoutingRepository,
        group="identity",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(UserTagsRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresUserTagsRepository, pg_sessionmaker
        ),
    )
    user_tags_service = providers.Singleton(
        UserTagsService, user_tags_repo=user_tags_repo
    )
    crypto = providers.Singleton(Crypto, settings.auth_settings.AES_HEX_KEY)
    # defined early: the workspace twin composes over it (identity → actions)
    action_repository = providers.Singleton(
        RoutingRepository,
        group="actions",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(ActionRepository, crypto=crypto),
    )

    # Repositories

    coupon_repository: CouponRepository = providers.Singleton(
        RoutingRepository,
        group="refdata",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        postgres=providers.Singleton(
            postgres_repository, PostgresCouponRepository, pg_sessionmaker
        ),
        mongo=providers.Singleton(CouponRepository),
    )
    workspace_user_repo: WorkspaceUserRepository = providers.Singleton(
        RoutingRepository,
        group="identity",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceUserRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresWorkspaceUserRepository, pg_sessionmaker
        ),
    )
    workspace_repo: WorkspaceRepository = providers.Singleton(
        RoutingRepository,
        group="identity",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresWorkspaceRepository, pg_sessionmaker, action_repository
        ),
    )
    allowed_origins_repo: AllowedOriginsRepository = providers.Singleton(
        RoutingRepository,
        group="refdata",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        postgres=providers.Singleton(
            postgres_repository, PostgresAllowedOriginsRepository, pg_sessionmaker
        ),
        mongo=providers.Singleton(AllowedOriginsRepository),
    )
    blacklisted_refresh_token_repo: BlacklistedRefreshTokenRepository = (
        providers.Singleton(
            RoutingRepository,
            group="identity",
            flags=flags,
            on_mirror_failure=outbox_recorder,
            mirror_timeout_s=mirror_timeout_s,
            mongo=providers.Singleton(BlacklistedRefreshTokenRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresBlacklistedRefreshTokenRepository, pg_sessionmaker
        ),
        )
    )

    form_response_repo: FormResponseRepository = providers.Singleton(
        RoutingRepository,
        group="responses",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(FormResponseRepository, crypto=crypto),
    )
    flow_event_repo: FlowEventRepository = providers.Singleton(
        RoutingRepository,
        group="analytics",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(FlowEventRepository),
    )
    form_ai_insight_repo = providers.Singleton(
        RoutingRepository,
        group="ai",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(FormAIInsightRepository),
    )
    form_ai_session_repo = providers.Singleton(
        RoutingRepository,
        group="ai",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(FormAISessionRepository),
    )
    workspace_ai_profile_repo = providers.Singleton(
        RoutingRepository,
        group="ai",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceAIProfileRepository),
    )
    workspace_api_key_repo = providers.Singleton(
        RoutingRepository,
        group="identity",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceAPIKeyRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresWorkspaceAPIKeyRepository, pg_sessionmaker
        ),
    )
    ai_preference_memory_repo = providers.Singleton(
        RoutingRepository,
        group="ai",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(AIPreferenceMemoryRepository),
    )

    form_provider_repo: FormPluginProviderRepository = providers.Singleton(
        RoutingRepository,
        group="refdata",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        postgres=providers.Singleton(
            postgres_repository, PostgresFormPluginProviderRepository, pg_sessionmaker
        ),
        mongo=providers.Singleton(FormPluginProviderRepository),
    )

    responder_groups_repository = providers.Singleton(
        RoutingRepository,
        group="responses",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(ResponderGroupsRepository),
    )
    # after responder_groups_repository / form_response_repo: the forms twins compose over them
    form_repo: FormRepository = providers.Singleton(
        RoutingRepository,
        group="forms",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(FormRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresFormRepository, pg_sessionmaker, responder_groups_repository, form_response_repo
        ),
    )
    workspace_form_repo: WorkspaceFormRepository = providers.Singleton(
        RoutingRepository,
        group="forms",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceFormRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresWorkspaceFormRepository, pg_sessionmaker, responder_groups_repository
        ),
    )

    integration_action_service: IntegrationActionService = providers.Singleton(
        IntegrationActionService, form_repo=form_repo
    )
    mcp_audit_log_repo: McpAuditLogRepository = providers.Singleton(
        RoutingRepository,
        group="ai",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(McpAuditLogRepository),
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
        form_repo=form_repo,
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
        form_repo=form_repo,
        workspace_form_repo=workspace_form_repo,
        workspace_user_repo=workspace_user_repo,
        aws_service=aws_service,
    )

    workspace_user_service: WorkspaceUserService = providers.Singleton(
        WorkspaceUserService,
        workspace_user_repository=workspace_user_repo,
        workspace_repo=workspace_repo,
    )

    job_store = providers.Singleton(MongoDBJobStore, host=settings.mongo_settings.URI)

    job_stores = providers.Dict(default=job_store)

    schedular = providers.Singleton(
        AsyncIOScheduler,
        jobstores=job_stores,
    )

    form_import_service: FormImportService = providers.Singleton(
        FormImportService,
        form_service=form_service,
        workspace_repo=workspace_repo,
        form_response_repo=form_response_repo,
    )

    form_schedular = providers.Singleton(
        FormSchedular,
        form_provider_service=form_provider_service,
        form_import_service=form_import_service,
        jwt_service=jwt_service,
        temporal_service=temporal_service,
        form_response_service=form_response_service,
        workspace_form_repo=workspace_form_repo,
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
        form_repo=form_repo,
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
        form_repo=form_repo,
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
        workspace_user_repo=workspace_user_repo,
        allowed_origins_repo=allowed_origins_repo,
        aws_service=aws_service,
        workspace_user_service=workspace_user_service,
        workspace_form_service=workspace_form_service,
        form_response_service=form_response_service,
        responder_groups_service=responder_groups_service,
        user_tags_service=user_tags_service,
    )

    ai_profile_service: AIProfileService = providers.Singleton(
        AIProfileService,
        workspace_user_service=workspace_user_service,
        profile_repo=workspace_ai_profile_repo,
    )

    ai_memory_service: AIMemoryService = providers.Singleton(AIMemoryService)

    api_key_service: APIKeyService = providers.Singleton(
        APIKeyService,
        workspace_user_service=workspace_user_service,
        api_key_repo=workspace_api_key_repo,
    )

    openai_service: OpenAIService = providers.Singleton(
        OpenAIService,
        workspace_service=workspace_service,
        workspace_form_service=workspace_form_service,
    )

    form_ai_chat_service: FormAIChatService = providers.Singleton(
        FormAIChatService,
        workspace_user_service=workspace_user_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        session_repo=form_ai_session_repo,
        # Bound late so the resolver sees openai_service's registry (incl. the
        # OpenAI-compatible provider when configured).
        provider_resolver=providers.Callable(
            lambda svc: svc._get_provider, openai_service
        ),
    )

    form_ai_review_service: FormAIReviewService = providers.Singleton(
        FormAIReviewService,
        workspace_user_service=workspace_user_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        provider_resolver=providers.Callable(
            lambda svc: svc._get_provider, openai_service
        ),
    )

    form_ai_insights_service: FormAIInsightsService = providers.Singleton(
        FormAIInsightsService,
        workspace_user_service=workspace_user_service,
        form_repo=form_repo,
        workspace_form_repo=workspace_form_repo,
        form_response_repo=form_response_repo,
        insight_repo=form_ai_insight_repo,
        provider_resolver=providers.Callable(
            lambda svc: svc._get_provider, openai_service
        ),
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
        RoutingRepository,
        group="identity",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceInvitationRepo),
        postgres=providers.Singleton(
            postgres_repository, PostgresWorkspaceInvitationRepo, pg_sessionmaker
        ),
    )

    workspace_members_service: WorkspaceMembersService = providers.Singleton(
        WorkspaceMembersService,
        workspace_user_service=workspace_user_service,
        workspace_invitation_repo=workspace_invitation_repo,
        workspace_repo=workspace_repo,
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

    workspace_responders_repo = providers.Singleton(
        RoutingRepository,
        group="responses",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceRespondersRepository),
    )
    workspace_responders_service = providers.Singleton(
        WorkspaceRespondersService,
        workspace_responders_repo=workspace_responders_repo,
        workspace_user_service=workspace_user_service,
        form_response_service=form_response_service,
    )
    workspace_consent_repo = providers.Singleton(
        RoutingRepository,
        group="forms",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(WorkspaceConsentRepo),
        postgres=providers.Singleton(
            postgres_repository, PostgresWorkspaceConsentRepo, pg_sessionmaker
        ),
    )

    workspace_consent_service = providers.Singleton(
        WorkspaceConsentService,
        workspace_user_service=workspace_user_service,
        workspace_consent_repo=workspace_consent_repo,
    )

    form_template_repo = providers.Singleton(
        RoutingRepository,
        group="forms",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(FormTemplateRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresFormTemplateRepository, pg_sessionmaker, workspace_repo
        ),
    )

    form_template_service = providers.Singleton(
        FormTemplateService,
        workspace_user_service=workspace_user_service,
        form_template_repo=form_template_repo,
        workspace_form_service=workspace_form_service,
        aws_service=aws_service,
        temporal_service=temporal_service,
    )

    user_feedback_repo = providers.Singleton(
        RoutingRepository,
        group="refdata",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        postgres=providers.Singleton(
            postgres_repository, PostgresUserFeedbackRepo, pg_sessionmaker
        ),
        mongo=providers.Singleton(UserFeedbackRepo),
    )

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

    media_library_repo = providers.Singleton(
        RoutingRepository,
        group="forms",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        mongo=providers.Singleton(MediaLibraryRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresMediaLibraryRepository, pg_sessionmaker
        ),
    )

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
        form_repo=form_repo,
    )

    form_actions_service: FormActionsService = providers.Singleton(
        FormActionsService, form_repo=form_repo
    )

    refresh_allowed_origins = providers.Callable(
        DynamicCORSMiddleware.force_refresh_origins
    )


container = AppContainer()
