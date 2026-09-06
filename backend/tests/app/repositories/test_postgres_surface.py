"""Every Postgres twin exposes at least the public surface of its Mongo original.

The RoutingRepository dispatches by attribute name, so a method missing on
the twin would surface as a mirror failure (or an AttributeError when the
group is served from Postgres). No database needed.
"""

import inspect

import pytest

from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.blacklisted_refresh_token_repository import (
    BlacklistedRefreshTokenRepository,
)
from backend.app.repositories.coupon_repository import CouponRepository
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.media_library_repository import MediaLibraryRepository
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresFormTemplateRepository,
    PostgresMediaLibraryRepository,
    PostgresWorkspaceConsentRepo,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.template import FormTemplateRepository
from backend.app.repositories.workspace_consent_repo import WorkspaceConsentRepo
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.ai_preference_memory_repository import (
    AIPreferenceMemoryRepository,
)
from backend.app.repositories.flow_event_repository import FlowEventRepository
from backend.app.repositories.form_ai_insight_repository import FormAIInsightRepository
from backend.app.repositories.form_ai_session_repository import FormAISessionRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.mcp_audit_log_repository import McpAuditLogRepository
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.ai import (
    PostgresAIPreferenceMemoryRepository,
    PostgresFlowEventRepository,
    PostgresFormAIInsightRepository,
    PostgresFormAISessionRepository,
    PostgresMcpAuditLogRepository,
    PostgresWorkspaceAIProfileRepository,
)
from backend.app.repositories.postgres.responses import (
    PostgresFormResponseRepository,
    PostgresResponderGroupsRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.repositories.workspace_ai_profile_repository import (
    WorkspaceAIProfileRepository,
)
from backend.app.repositories.workspace_responders_repository import (
    WorkspaceRespondersRepository,
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
from backend.app.repositories.user_feedback import UserFeedbackRepo
from backend.app.repositories.user_tags_repository import UserTagsRepository
from backend.app.repositories.workspace_api_key_repository import (
    WorkspaceAPIKeyRepository,
)
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from common.db import is_write_op

PAIRS = [
    (AllowedOriginsRepository, PostgresAllowedOriginsRepository),
    (FormPluginProviderRepository, PostgresFormPluginProviderRepository),
    (CouponRepository, PostgresCouponRepository),
    (UserFeedbackRepo, PostgresUserFeedbackRepo),
    (WorkspaceRepository, PostgresWorkspaceRepository),
    (WorkspaceUserRepository, PostgresWorkspaceUserRepository),
    (WorkspaceInvitationRepo, PostgresWorkspaceInvitationRepo),
    (WorkspaceAPIKeyRepository, PostgresWorkspaceAPIKeyRepository),
    (BlacklistedRefreshTokenRepository, PostgresBlacklistedRefreshTokenRepository),
    (UserTagsRepository, PostgresUserTagsRepository),
    (FormRepository, PostgresFormRepository),
    (WorkspaceFormRepository, PostgresWorkspaceFormRepository),
    (WorkspaceConsentRepo, PostgresWorkspaceConsentRepo),
    (FormTemplateRepository, PostgresFormTemplateRepository),
    (MediaLibraryRepository, PostgresMediaLibraryRepository),
    (FormResponseRepository, PostgresFormResponseRepository),
    (ResponderGroupsRepository, PostgresResponderGroupsRepository),
    (WorkspaceRespondersRepository, PostgresWorkspaceRespondersRepository),
    (ActionRepository, PostgresActionRepository),
    (FlowEventRepository, PostgresFlowEventRepository),
    (FormAIInsightRepository, PostgresFormAIInsightRepository),
    (FormAISessionRepository, PostgresFormAISessionRepository),
    (WorkspaceAIProfileRepository, PostgresWorkspaceAIProfileRepository),
    (AIPreferenceMemoryRepository, PostgresAIPreferenceMemoryRepository),
    (McpAuditLogRepository, PostgresMcpAuditLogRepository),
]


def public_methods(cls):
    return {
        name
        for name, member in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_") and name in cls.__dict__
    }


@pytest.mark.parametrize("mongo, postgres", PAIRS, ids=lambda c: c.__name__)
def test_twin_covers_the_mongo_surface(mongo, postgres):
    missing = public_methods(mongo) - public_methods(postgres)
    assert not missing, f"{postgres.__name__} lacks {sorted(missing)}"


@pytest.mark.parametrize("mongo, postgres", PAIRS, ids=lambda c: c.__name__)
def test_twin_methods_are_not_marked_themselves(mongo, postgres):
    """Routing reads the markers off the Mongo surface; a marker on the twin is
    a sign the two classes have drifted apart."""
    marked = [n for n in public_methods(postgres) if is_write_op(getattr(postgres, n))]
    assert marked == []
