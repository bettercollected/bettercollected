import os
from pathlib import Path

from concurrent.futures.thread import ThreadPoolExecutor

from common.configs.crypto import Crypto
from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService
from dependency_injector import containers, providers

from common.db import DatabaseSettings

from backend.db.groups import load_backend_flags
from backend.jobs.app import app as jobs_app
from backend.db.session import (
    LazyRepository,
    build_engine,
    build_sessionmaker,
)
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.ai import (
    PostgresAIPreferenceMemoryRepository,
    PostgresCreateFormPromptRepository,
    PostgresFormAIInsightRepository,
    PostgresFormAISessionRepository,
    PostgresIdempotencyRepository,
    PostgresMcpAuditLogRepository,
    PostgresWorkspaceAIProfileRepository,
)
from backend.app.repositories.postgres.responses import (
    PostgresFormResponseRepository,
    PostgresResponderGroupsRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.repositories.postgres.forms import (
    PostgresFormImportRepository,
    PostgresFormRepository,
    PostgresFormTemplateRepository,
    PostgresMediaLibraryRepository,
    PostgresWorkspaceConsentRepo,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.postgres.identity import (
    PostgresSessionRepository,
    PostgresUserTagsRepository,
    PostgresWorkspaceAPIKeyRepository,
    PostgresWorkspaceDomainRepository,
    PostgresSsoConnectionRepository,
    PostgresSsoUsedStateRepository,
    PostgresScimDirectoryRepository,
    PostgresScimEventRepository,
    PostgresScimGroupMemberRepository,
    PostgresScimGroupRepository,
    PostgresScimUserRepository,
    PostgresWorkspaceInvitationRepo,
    PostgresWorkspaceRepository,
    PostgresWorkspaceUserRepository,
)
from backend.app.repositories.postgres.registration import (
    PostgresFormRegistrationRepository,
    PostgresRegistrationDeliveryRepository,
    PostgresRegistrationServiceRepository,
)
from backend.app.repositories.postgres.analytics import (
    PostgresFlowEventRepository,
    PostgresRateLimitRepository,
)
from backend.app.repositories.postgres.refdata import (
    PostgresAllowedOriginsRepository,
    PostgresCouponRepository,
    PostgresFormPluginProviderRepository,
    PostgresPriceSuggestionRepository,
    PostgresUserFeedbackRepo,
)

from backend.app.schedulers.form_schedular import FormSchedular
from backend.app.services.actions_service import ActionService
from backend.app.services.sheets_grant_revocation import SheetsGrantService
from backend.app.services.sheets_reconsent import SheetsReconsentService
from backend.app.services.auth_service import AuthService
from backend.app.services.case_duplicate_accounts import CaseDuplicateAccounts
from backend.app.services.session_service import SessionService
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.coupon_service import CouponService
from backend.app.services.feedback_service import UserFeedbackService
from backend.app.services.form_import_service import FormImportService
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.form_service import FormService
from backend.app.services.media_library_service import MediaLibraryService
from backend.app.services.image_service import ImageService
from backend.app.services.ai.api_keys import APIKeyService
from backend.app.services.ai.chat import FormAIChatService
from backend.app.services.ai.proposals import FormAIProposalService
from backend.app.services.ai.consent import AIConsentService
from backend.app.services.ai.memory import AIMemoryService
from backend.app.services.ai.profile import AIProfileService
from backend.app.services.ai.insights import FormAIInsightsService
from backend.app.services.ai.review import FormAIReviewService
from backend.app.services.ai.usage import AIUsageGuard
from backend.app.services.openai_service import OpenAIService
from backend.app.services.ai.outline_service import FormOutlineService
from backend.app.services.integration_action_service import IntegrationActionService
from backend.app.services.integration_provider_factory import IntegrationProviderFactory
from backend.app.services.integration_service import IntegrationService
from backend.app.services.flow_event_service import FlowEventService
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.app.services.respondent_feedback_service import (
    RespondentFeedbackService,
)
from backend.app.services.plugin_proxy_service import PluginProxyService
from backend.app.services.price_suggestion import PriceSuggestionService
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.stripe_service import StripeService
from backend.app.services.template_service import FormTemplateService
from backend.app.services.credential_purge import CredentialPurgeService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.user_tags_service import UserTagsService
from backend.app.services.workspace_consent_service import WorkspaceConsentService
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_members_service import WorkspaceMembersService
from backend.app.services.workspace_responders_service import WorkspaceRespondersService
from backend.app.services.custom_domain_service import CustomDomainService
from backend.app.services.pdf_import.pipeline import ImportPipeline
from backend.app.services.pdf_import.storage import S3ObjectStore
from backend.app.services.open_formulieren_import_service import (
    OpenFormulierenImportService,
)
from backend.app.services.pdf_import_service import PdfImportService
from backend.app.services.workspace_service import WorkspaceService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.registration.service import RegistrationService
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.app.services.sso.connection_service import SsoConnectionService
from backend.app.services.sso.login_service import SsoLoginService
from backend.app.services.sso.policy import SsoPolicyService
from backend.app.services.sso.polis_client import PolisAdminClient
from backend.app.services.scim.directory_service import ScimDirectoryService
from backend.app.services.scim.polis_dsync import PolisDirectoryClient
from backend.app.services.scim.sync_service import ScimSyncService
from backend.app.services.scim.webhook_service import ScimWebhookService
from backend.app.services.umami_client import UmamiClient
from backend.app.services.analytics_service import AnalyticsService

from backend.app.services.form_actions_service import FormActionsService
from backend.app.services.form_spec.editor_ops import EditorOpsService
from backend.app.services.form_spec.service import FormSpecService
from backend.app.services.form_spec.writes import FormSpecWriter
from backend.app.services.idempotency import IdempotencyService
from backend.app.middlewares.dynamic_cors_middleware import DynamicCORSMiddleware
from backend.config import settings

current_path = Path(os.path.abspath(os.path.dirname(__file__))).absolute()


class AppContainer(containers.DeclarativeContainer):
    http_client: HttpClient = providers.Singleton(HttpClient)

    # Postgres is the only store. The flags are read once at boot: the jobs
    # backends, and a stale store setting left from the 4.0 cutover (for a group
    # of backend.db.groups.POSTGRES_ONLY_GROUPS) refuses to start.
    flags = providers.Singleton(load_backend_flags)
    # The engine and sessions exist only when DATABASE_URL is set; startup
    # refuses to run without it (backend.db.startup).
    db_settings = providers.Singleton(DatabaseSettings.from_env)
    pg_engine = providers.Singleton(build_engine, db_settings)
    pg_sessionmaker = providers.Singleton(build_sessionmaker, pg_engine)

    user_tags_repo: PostgresUserTagsRepository = providers.Singleton(
        PostgresUserTagsRepository, pg_sessionmaker
    )
    user_tags_service = providers.Singleton(
        UserTagsService, user_tags_repo=user_tags_repo
    )
    crypto = providers.Singleton(Crypto, settings.auth_settings.AES_HEX_KEY)
    # defined early: the workspace repository composes over it (identity →
    # actions, get_workspace_with_action_by_id)
    action_repository: PostgresActionRepository = providers.Singleton(
        PostgresActionRepository, pg_sessionmaker, crypto
    )

    # Repositories

    coupon_repository: PostgresCouponRepository = providers.Singleton(
        PostgresCouponRepository, pg_sessionmaker
    )
    workspace_user_repo: PostgresWorkspaceUserRepository = providers.Singleton(
        PostgresWorkspaceUserRepository, pg_sessionmaker
    )
    workspace_repo: PostgresWorkspaceRepository = providers.Singleton(
        PostgresWorkspaceRepository, pg_sessionmaker, action_repository
    )
    allowed_origins_repo: PostgresAllowedOriginsRepository = providers.Singleton(
        PostgresAllowedOriginsRepository, pg_sessionmaker
    )
    session_repo: PostgresSessionRepository = providers.Singleton(
        PostgresSessionRepository, pg_sessionmaker
    )

    flow_event_repo: PostgresFlowEventRepository = providers.Singleton(
        PostgresFlowEventRepository, pg_sessionmaker
    )
    rate_limit_repo: PostgresRateLimitRepository = providers.Singleton(
        PostgresRateLimitRepository, pg_sessionmaker
    )
    form_ai_insight_repo: PostgresFormAIInsightRepository = providers.Singleton(
        PostgresFormAIInsightRepository, pg_sessionmaker
    )
    form_ai_session_repo: PostgresFormAISessionRepository = providers.Singleton(
        PostgresFormAISessionRepository, pg_sessionmaker
    )
    workspace_ai_profile_repo: PostgresWorkspaceAIProfileRepository = providers.Singleton(
        PostgresWorkspaceAIProfileRepository, pg_sessionmaker
    )
    form_import_repo: PostgresFormImportRepository = providers.Singleton(
        PostgresFormImportRepository, pg_sessionmaker
    )
    workspace_domain_repo: PostgresWorkspaceDomainRepository = providers.Singleton(
        PostgresWorkspaceDomainRepository, pg_sessionmaker
    )
    registration_service_repo: PostgresRegistrationServiceRepository = providers.Singleton(
        PostgresRegistrationServiceRepository, pg_sessionmaker
    )
    form_registration_repo: PostgresFormRegistrationRepository = providers.Singleton(
        PostgresFormRegistrationRepository, pg_sessionmaker
    )
    registration_delivery_repo: PostgresRegistrationDeliveryRepository = providers.Singleton(
        PostgresRegistrationDeliveryRepository, pg_sessionmaker
    )
    sso_connection_repo: PostgresSsoConnectionRepository = providers.Singleton(
        PostgresSsoConnectionRepository, pg_sessionmaker
    )
    sso_used_state_repo: PostgresSsoUsedStateRepository = providers.Singleton(
        PostgresSsoUsedStateRepository, pg_sessionmaker
    )
    scim_directory_repo: PostgresScimDirectoryRepository = providers.Singleton(
        PostgresScimDirectoryRepository, pg_sessionmaker
    )
    scim_user_repo: PostgresScimUserRepository = providers.Singleton(
        PostgresScimUserRepository, pg_sessionmaker
    )
    scim_group_repo: PostgresScimGroupRepository = providers.Singleton(
        PostgresScimGroupRepository, pg_sessionmaker
    )
    scim_group_member_repo: PostgresScimGroupMemberRepository = providers.Singleton(
        PostgresScimGroupMemberRepository, pg_sessionmaker
    )
    scim_event_repo: PostgresScimEventRepository = providers.Singleton(
        PostgresScimEventRepository, pg_sessionmaker
    )
    workspace_api_key_repo: PostgresWorkspaceAPIKeyRepository = providers.Singleton(
        PostgresWorkspaceAPIKeyRepository, pg_sessionmaker
    )
    ai_preference_memory_repo: PostgresAIPreferenceMemoryRepository = providers.Singleton(
        PostgresAIPreferenceMemoryRepository, pg_sessionmaker
    )

    form_provider_repo: PostgresFormPluginProviderRepository = providers.Singleton(
        PostgresFormPluginProviderRepository, pg_sessionmaker
    )

    # the forms repositories compose over this one and it over theirs
    # (a form's title and importer): resolved lazily
    form_response_repo: PostgresFormResponseRepository = providers.Singleton(
        PostgresFormResponseRepository,
        pg_sessionmaker,
        LazyRepository(lambda: container.form_repo()),
        LazyRepository(lambda: container.workspace_form_repo()),
    )

    responder_groups_repository: PostgresResponderGroupsRepository = providers.Singleton(
        PostgresResponderGroupsRepository, pg_sessionmaker
    )
    # after responder_groups_repository / form_response_repo: the forms
    # repositories compose over them
    form_repo: PostgresFormRepository = providers.Singleton(
        PostgresFormRepository,
        pg_sessionmaker,
        responder_groups_repository,
        form_response_repo,
    )
    workspace_form_repo: PostgresWorkspaceFormRepository = providers.Singleton(
        PostgresWorkspaceFormRepository,
        pg_sessionmaker,
        responder_groups_repository,
    )

    rate_limiter: FixedWindowRateLimiter = providers.Singleton(
        FixedWindowRateLimiter,
        repo=rate_limit_repo,
        secret=settings.auth_settings.JWT_SECRET,
    )
    flow_event_service: FlowEventService = providers.Singleton(
        FlowEventService,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        flow_event_repo=flow_event_repo,
        rate_limiter=rate_limiter,
    )
    # rate limits and the daily budget of the AI endpoints
    ai_usage_guard: AIUsageGuard = providers.Singleton(
        AIUsageGuard, limiter=rate_limiter
    )

    # Every workspace-scoped access decision (services call authorize()).
    authorization_service: AuthorizationService = providers.Singleton(
        AuthorizationService,
        workspace_repo=workspace_repo,
        workspace_user_repo=workspace_user_repo,
        workspace_form_repo=workspace_form_repo,
    )

    mcp_audit_log_repo: PostgresMcpAuditLogRepository = providers.Singleton(
        PostgresMcpAuditLogRepository, pg_sessionmaker
    )
    # the prompts AI-generated forms were built from (services/openai_service.py)
    create_form_prompt_repo: PostgresCreateFormPromptRepository = providers.Singleton(
        PostgresCreateFormPromptRepository, pg_sessionmaker
    )
    # the public API's Idempotency-Key records (services/idempotency.py)
    idempotency_repo: PostgresIdempotencyRepository = providers.Singleton(
        PostgresIdempotencyRepository, pg_sessionmaker
    )

    temporal_service = providers.Singleton(
        TemporalService,
        server_uri=settings.temporal_settings.server_uri,
        namespace=settings.temporal_settings.namespace,
        crypto=crypto,
        flags=flags,
        jobs=providers.Object(jobs_app),
    )

    # after re-consent: the new Sheets grant stored, the legacy one revoked
    # (services/sheets_grant_revocation.py)
    sheets_grant_service: SheetsGrantService = providers.Singleton(
        SheetsGrantService,
        form_repo=form_repo,
        crypto=crypto,
        temporal_service=temporal_service,
    )
    integration_action_service: IntegrationActionService = providers.Singleton(
        IntegrationActionService,
        form_repo=form_repo,
        sheets_grants=sheets_grant_service,
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
        authorization_service=authorization_service,
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
        authorization_service=authorization_service,
        aws_service=aws_service,
        workspace_repo=workspace_repo,
        registration_delivery_repo=registration_delivery_repo,
    )

    respondent_feedback_service: RespondentFeedbackService = providers.Singleton(
        RespondentFeedbackService,
        form_response_repo=form_response_repo,
        form_repo=form_repo,
        workspace_form_repo=workspace_form_repo,
        authorization_service=authorization_service,
        workspace_repo=workspace_repo,
        http_client=http_client,
    )

    workspace_user_service: WorkspaceUserService = providers.Singleton(
        WorkspaceUserService,
        workspace_user_repository=workspace_user_repo,
        workspace_repo=workspace_repo,
    )

    form_import_service: FormImportService = providers.Singleton(
        FormImportService,
        form_service=form_service,
        workspace_repo=workspace_repo,
        form_response_repo=form_response_repo,
        workspace_form_repo=workspace_form_repo,
    )

    form_schedular = providers.Singleton(
        FormSchedular,
        temporal_service=temporal_service,
        form_response_service=form_response_service,
    )

    responder_groups_service = providers.Singleton(
        ResponderGroupsService,
        responder_groups_repo=responder_groups_repository,
        authorization_service=authorization_service,
        form_service=form_service,
    )

    sheets_reconsent_service = providers.Singleton(
        SheetsReconsentService,
        form_repo=form_repo,
        workspace_repo=workspace_repo,
        crypto=crypto,
        http_client=http_client,
    )

    action_service = providers.Singleton(
        ActionService,
        action_repository=action_repository,
        form_repo=form_repo,
        temporal_service=temporal_service,
        authorization_service=authorization_service,
        http_client=http_client,
        form_provider_service=form_provider_service,
        form_response_service=form_response_service,
        workspace_repo=workspace_repo,
        sheets_reconsent=sheets_reconsent_service,
    )

    workspace_form_service: WorkspaceFormService = providers.Singleton(
        WorkspaceFormService,
        form_provider_service=form_provider_service,
        plugin_proxy_service=plugin_proxy_service,
        authorization_service=authorization_service,
        form_service=form_service,
        workspace_form_repository=workspace_form_repo,
        form_repo=form_repo,
        form_import_service=form_import_service,
        form_response_service=form_response_service,
        responder_groups_service=responder_groups_service,
        user_tags_service=user_tags_service,
        temporal_service=temporal_service,
        aws_service=aws_service,
        action_service=action_service,
        crypto=crypto,
        form_template_repo=LazyRepository(lambda: container.form_template_repo()),
        pdf_import_repo=form_import_repo,
        # the registration service needs this service's neighbours: looked up per call
        registration_service=LazyRepository(lambda: container.registration_service()),
    )

    registration_service: RegistrationService = providers.Singleton(
        RegistrationService,
        authorization_service=authorization_service,
        service_repo=registration_service_repo,
        registration_repo=form_registration_repo,
        delivery_repo=registration_delivery_repo,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        form_response_service=form_response_service,
        workspace_repo=workspace_repo,
        crypto=crypto,
        aws_service=aws_service,
    )

    pdf_import_store = providers.Singleton(
        S3ObjectStore, aws_service=aws_service, bucket=settings.aws_settings.BUCKET
    )
    pdf_import_pipeline = providers.Singleton(
        ImportPipeline,
        repo=form_import_repo,
        store=pdf_import_store,
        settings=settings.pdf_import,
        # workspace id -> the consented AI provider, through the same opt-in
        # check as every other AI path (openai_service is defined further
        # down this container, so it is looked up per run)
        # (the upload was admitted to the AI limits: the job only counts tokens)
        provider_resolver=providers.Object(
            lambda workspace_id: container.openai_service().provider_for_workspace(
                workspace_id, admit=False
            )
        ),
        form_repo=form_repo,
        workspace_form_service=workspace_form_service,
    )
    pdf_import_service: PdfImportService = providers.Singleton(
        PdfImportService,
        repo=form_import_repo,
        store=pdf_import_store,
        pipeline=pdf_import_pipeline,
        workspace_form_service=workspace_form_service,
        authorization_service=authorization_service,
        settings=settings.pdf_import,
        flags=flags,
        # an upload asking for AI structuring counts as one AI request
        ai_admission=providers.Object(
            lambda workspace_id, user: container.openai_service().admit_import(
                workspace_id, user
            )
        ),
    )

    open_formulieren_import_service: OpenFormulierenImportService = (
        providers.Singleton(
            OpenFormulierenImportService,
            repo=form_import_repo,
            workspace_form_service=workspace_form_service,
            workspace_form_repo=workspace_form_repo,
            authorization_service=authorization_service,
        )
    )

    custom_domain_service: CustomDomainService = providers.Singleton(
        CustomDomainService, settings=settings.custom_domain
    )

    workspace_domain_service: WorkspaceDomainService = providers.Singleton(
        WorkspaceDomainService,
        authorization_service=authorization_service,
        domain_repo=workspace_domain_repo,
    )

    sso_policy_service: SsoPolicyService = providers.Singleton(
        SsoPolicyService,
        workspace_repo=workspace_repo,
        domain_service=workspace_domain_service,
        connection_repo=sso_connection_repo,
        http_client=http_client,
        workspace_user_repo=workspace_user_repo,
    )

    workspace_service: WorkspaceService = providers.Singleton(
        WorkspaceService,
        sso_policy=sso_policy_service,
        # defined further down (it needs the session service)
        sso_release=providers.Object(
            lambda workspace_ids: _release_sso_and_scim(workspace_ids)
        ),
        http_client=http_client,
        custom_domain_service=custom_domain_service,
        workspace_repo=workspace_repo,
        workspace_user_repo=workspace_user_repo,
        allowed_origins_repo=allowed_origins_repo,
        aws_service=aws_service,
        workspace_user_service=workspace_user_service,
        authorization_service=authorization_service,
        workspace_form_service=workspace_form_service,
        form_response_service=form_response_service,
        responder_groups_service=responder_groups_service,
        user_tags_service=user_tags_service,
        workspace_domain_service=workspace_domain_service,
        registration_service=registration_service,
    )

    ai_profile_service: AIProfileService = providers.Singleton(
        AIProfileService,
        authorization_service=authorization_service,
        profile_repo=workspace_ai_profile_repo,
    )

    ai_memory_service: AIMemoryService = providers.Singleton(AIMemoryService)

    api_key_service: APIKeyService = providers.Singleton(
        APIKeyService,
        authorization_service=authorization_service,
        api_key_repo=workspace_api_key_repo,
    )

    ai_consent_service: AIConsentService = providers.Singleton(
        AIConsentService,
        workspace_repo=workspace_repo,
        authorization_service=authorization_service,
    )

    openai_service: OpenAIService = providers.Singleton(
        OpenAIService,
        workspace_service=workspace_service,
        workspace_form_service=workspace_form_service,
        authorization_service=authorization_service,
        ai_consent_service=ai_consent_service,
        ai_usage_guard=ai_usage_guard,
        create_form_prompt_repo=create_form_prompt_repo,
    )

    form_outline_service: FormOutlineService = providers.Singleton(
        FormOutlineService,
        openai_service=openai_service,
        workspace_form_service=workspace_form_service,
        authorization_service=authorization_service,
        ai_consent_service=ai_consent_service,
        ai_usage_guard=ai_usage_guard,
    )

    form_ai_chat_service: FormAIChatService = providers.Singleton(
        FormAIChatService,
        authorization_service=authorization_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        session_repo=form_ai_session_repo,
        # Bound late so the resolver sees openai_service's registry (incl. the
        # OpenAI-compatible provider when configured).
        provider_resolver=providers.Callable(
            lambda svc: svc.provider_for_workspace, openai_service
        ),
    )

    # accept / reject the chat's proposals (no provider call)
    form_ai_proposal_service: FormAIProposalService = providers.Singleton(
        FormAIProposalService,
        authorization_service=authorization_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        session_repo=form_ai_session_repo,
        rate_limiter=rate_limiter,
        ai_usage_guard=ai_usage_guard,
    )

    form_ai_review_service: FormAIReviewService = providers.Singleton(
        FormAIReviewService,
        authorization_service=authorization_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        ai_usage_guard=ai_usage_guard,
        provider_resolver=providers.Callable(
            lambda svc: svc.provider_for_workspace, openai_service
        ),
    )

    form_ai_insights_service: FormAIInsightsService = providers.Singleton(
        FormAIInsightsService,
        authorization_service=authorization_service,
        form_repo=form_repo,
        workspace_form_repo=workspace_form_repo,
        form_response_repo=form_response_repo,
        insight_repo=form_ai_insight_repo,
        provider_resolver=providers.Callable(
            lambda svc: svc.provider_for_workspace, openai_service
        ),
        ai_consent_service=ai_consent_service,
        form_response_service=form_response_service,
    )

    session_service: SessionService = providers.Singleton(
        SessionService, session_repo=session_repo, sso_policy=sso_policy_service
    )

    # a deleted account's stored provider credentials (services/credential_purge.py)
    credential_purge_service: CredentialPurgeService = providers.Singleton(
        CredentialPurgeService,
        form_provider_service=form_provider_service,
        temporal_service=temporal_service,
        pg_engine=pg_engine,
    )

    auth_service: AuthService = providers.Singleton(
        AuthService,
        credential_purge_service=credential_purge_service,
        http_client=http_client,
        plugin_proxy_service=plugin_proxy_service,
        form_provider_service=form_provider_service,
        jwt_service=jwt_service,
        workspace_service=workspace_service,
        temporal_service=temporal_service,
        crypto=crypto,
        user_tags_service=user_tags_service,
        session_service=session_service,
        allowed_origins_repo=allowed_origins_repo,
        sso_policy=sso_policy_service,
    )

    # admin task auth.resolve_case_duplicate_accounts (admin_tasks_router)
    case_duplicate_accounts: CaseDuplicateAccounts = providers.Singleton(
        CaseDuplicateAccounts,
        http_client=http_client,
        workspace_repo=workspace_repo,
        workspace_form_repo=workspace_form_repo,
        auth_service=auth_service,
    )

    polis_admin_client: PolisAdminClient = providers.Singleton(
        PolisAdminClient, settings=settings.sso
    )

    sso_connection_service: SsoConnectionService = providers.Singleton(
        SsoConnectionService,
        authorization_service=authorization_service,
        connection_repo=sso_connection_repo,
        domain_service=workspace_domain_service,
        workspace_repo=workspace_repo,
        workspace_user_repo=workspace_user_repo,
        session_service=session_service,
        policy=sso_policy_service,
        polis=polis_admin_client,
        # defined further down
        on_default_role_changed=providers.Object(
            lambda workspace: container.scim_sync_service().recompute_workspace(
                workspace
            )
        ),
    )

    scim_sync_service: ScimSyncService = providers.Singleton(
        ScimSyncService,
        directory_repo=scim_directory_repo,
        user_repo=scim_user_repo,
        group_repo=scim_group_repo,
        member_repo=scim_group_member_repo,
        workspace_repo=workspace_repo,
        workspace_user_repo=workspace_user_repo,
        workspace_user_service=workspace_user_service,
        domain_service=workspace_domain_service,
        session_service=session_service,
        http_client=http_client,
    )

    polis_directory_client: PolisDirectoryClient = providers.Singleton(
        PolisDirectoryClient, settings=settings.sso
    )

    scim_directory_service: ScimDirectoryService = providers.Singleton(
        ScimDirectoryService,
        authorization_service=authorization_service,
        directory_repo=scim_directory_repo,
        user_repo=scim_user_repo,
        group_repo=scim_group_repo,
        member_repo=scim_group_member_repo,
        workspace_repo=workspace_repo,
        domain_service=workspace_domain_service,
        sync_service=scim_sync_service,
        polis=polis_directory_client,
        crypto=crypto,
    )

    scim_webhook_service: ScimWebhookService = providers.Singleton(
        ScimWebhookService,
        directory_repo=scim_directory_repo,
        event_repo=scim_event_repo,
        sync_service=scim_sync_service,
        crypto=crypto,
    )

    sso_login_service: SsoLoginService = providers.Singleton(
        SsoLoginService,
        directory_guard=scim_sync_service,
        http_client=http_client,
        connection_repo=sso_connection_repo,
        connection_service=sso_connection_service,
        domain_service=workspace_domain_service,
        workspace_repo=workspace_repo,
        workspace_user_service=workspace_user_service,
        authorization_service=authorization_service,
        auth_service=auth_service,
        used_state_repo=sso_used_state_repo,
    )

    workspace_invitation_repo: PostgresWorkspaceInvitationRepo = providers.Singleton(
        PostgresWorkspaceInvitationRepo, pg_sessionmaker
    )

    workspace_members_service: WorkspaceMembersService = providers.Singleton(
        WorkspaceMembersService,
        workspace_user_service=workspace_user_service,
        authorization_service=authorization_service,
        workspace_invitation_repo=workspace_invitation_repo,
        workspace_repo=workspace_repo,
        http_client=http_client,
        workspace_form_service=workspace_form_service,
        scim_directory_repo=scim_directory_repo,
    )

    stripe_service: StripeService = providers.Singleton(
        StripeService,
        http_client=http_client,
        plugin_proxy_service=plugin_proxy_service,
        form_provider_service=form_provider_service,
        jwt_service=jwt_service,
        workspace_service=workspace_service,
    )

    workspace_responders_repo: PostgresWorkspaceRespondersRepository = (
        providers.Singleton(PostgresWorkspaceRespondersRepository, pg_sessionmaker)
    )
    workspace_responders_service = providers.Singleton(
        WorkspaceRespondersService,
        workspace_responders_repo=workspace_responders_repo,
        authorization_service=authorization_service,
        form_response_service=form_response_service,
    )
    workspace_consent_repo: PostgresWorkspaceConsentRepo = providers.Singleton(
        PostgresWorkspaceConsentRepo, pg_sessionmaker
    )

    workspace_consent_service = providers.Singleton(
        WorkspaceConsentService,
        authorization_service=authorization_service,
        workspace_consent_repo=workspace_consent_repo,
    )

    # the titles of the workspaces templates were imported from: read
    # through the workspace repository
    form_template_repo: PostgresFormTemplateRepository = providers.Singleton(
        PostgresFormTemplateRepository, pg_sessionmaker, workspace_repo
    )

    form_template_service = providers.Singleton(
        FormTemplateService,
        authorization_service=authorization_service,
        form_template_repo=form_template_repo,
        workspace_form_service=workspace_form_service,
        aws_service=aws_service,
        temporal_service=temporal_service,
    )

    user_feedback_repo: PostgresUserFeedbackRepo = providers.Singleton(
        PostgresUserFeedbackRepo, pg_sessionmaker
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

    price_suggestion_repo: PostgresPriceSuggestionRepository = providers.Singleton(
        PostgresPriceSuggestionRepository, pg_sessionmaker
    )

    price_suggestion_service = providers.Singleton(
        PriceSuggestionService,
        auth_service=auth_service,
        workspace_service=workspace_service,
        price_suggestion_repo=price_suggestion_repo,
    )

    media_library_repo: PostgresMediaLibraryRepository = providers.Singleton(
        PostgresMediaLibraryRepository, pg_sessionmaker
    )

    media_library_service = providers.Singleton(
        MediaLibraryService,
        media_library_repo=media_library_repo,
        aws_service=aws_service,
        authorization_service=authorization_service,
    )
    # Unsplash through our server; image addresses copied into our storage
    image_service: ImageService = providers.Singleton(
        ImageService,
        aws_service=aws_service,
        rate_limiter=rate_limiter,
        authorization_service=authorization_service,
    )

    umami_client: UmamiClient = providers.Singleton(UmamiClient)

    analytics_service: AnalyticsService = providers.Singleton(
        AnalyticsService,
        authorization_service=authorization_service,
        workspace_repo=workspace_repo,
    )

    integration_service: IntegrationService = providers.Singleton(
        IntegrationService,
        form_provider_service=form_provider_service,
        crypto=crypto,
        http_client=http_client,
        integration_action_service=integration_action_service,
        form_repo=form_repo,
        workspace_form_repo=workspace_form_repo,
        authorization_service=authorization_service,
        action_repository=action_repository,
    )

    form_actions_service: FormActionsService = providers.Singleton(
        FormActionsService, form_repo=form_repo
    )

    refresh_allowed_origins = providers.Callable(
        DynamicCORSMiddleware.force_refresh_origins
    )

    # Form spec v1: validate documents, dry-run ops (stores nothing).
    form_spec_service: FormSpecService = providers.Singleton(
        FormSpecService,
        authorization_service=authorization_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
    )
    # The public API: forms from spec documents, Idempotency-Key records.
    form_spec_writer: FormSpecWriter = providers.Singleton(
        FormSpecWriter,
        form_spec_service=form_spec_service,
        workspace_form_service=workspace_form_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
    )
    idempotency_service: IdempotencyService = providers.Singleton(
        IdempotencyService, idempotency_repo=idempotency_repo
    )
    # The builder's op-batch save (session auth, If-Match, Idempotency-Key).
    editor_ops_service: EditorOpsService = providers.Singleton(
        EditorOpsService,
        authorization_service=authorization_service,
        workspace_form_repo=workspace_form_repo,
        form_repo=form_repo,
        idempotency_service=idempotency_service,
        rate_limiter=rate_limiter,
    )


container = AppContainer()


async def _release_sso_and_scim(workspace_ids):
    """A deleted workspace's SSO connections and SCIM directory, in Polis
    (best effort) and here."""
    await container.sso_connection_service().release_workspaces(workspace_ids)
    await container.scim_directory_service().release_workspaces(workspace_ids)
