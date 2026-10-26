"""Repository groups, all served from Postgres only since 4.1.

Their Mongo collections are read only by the import from 4.0
(``python -m backend.migrate``): the repositories have no Mongo side, no
routing, no mirror and no shadow read, and compose over each other where a
read crosses groups (backend.app.repositories.response_scope).
"""

import os
from typing import Mapping, Sequence

from common.db.flags import DbFlags, load_flags, refuse_stale_store_flags
from common.db.groups import BACKEND_GROUPS

GROUPS = BACKEND_GROUPS

#: Groups served from Postgres only: their repositories have no Mongo side and
#: no routing any more. Their collections are read only by the import from 4.0
#: (``python -m backend.migrate``).
POSTGRES_ONLY_GROUPS = (
    "refdata",
    "analytics",
    "ai",
    "actions",
    "identity",
    "forms",
    "responses",
)

#: The routed repositories of the Postgres-only groups as 4.0 named them (an
#: outbox entry names the repository, not the group). They are routed no
#: more; ``resolve-outbox`` counts their open entries as
#: ``postgres_only_leftover`` instead of keeping them as unknown.
RETIRED_REPOSITORIES = {
    "ActionRepository": "actions",
    **dict.fromkeys(
        (
            "AIPreferenceMemoryRepository",
            "CreateFormPromptRepository",
            "FormAIInsightRepository",
            "FormAISessionRepository",
            "IdempotencyRepository",
            "McpAuditLogRepository",
            "WorkspaceAIProfileRepository",
        ),
        "ai",
    ),
    **dict.fromkeys(("FlowEventRepository", "RateLimitRepository"), "analytics"),
    **dict.fromkeys(
        (
            "FormRepository",
            "FormImportRepository",
            "FormTemplateRepository",
            "MediaLibraryRepository",
            "WorkspaceConsentRepo",
            "WorkspaceFormRepository",
        ),
        "forms",
    ),
    **dict.fromkeys(
        (
            "FormResponseRepository",
            "ResponderGroupsRepository",
            "WorkspaceRespondersRepository",
        ),
        "responses",
    ),
    **dict.fromkeys(
        (
            "ScimDirectoryRepository",
            "ScimEventRepository",
            "ScimGroupMemberRepository",
            "ScimGroupRepository",
            "ScimUserRepository",
            "SessionRepository",
            "SsoConnectionRepository",
            "SsoUsedStateRepository",
            "UserTagsRepository",
            "WorkspaceAPIKeyRepository",
            "WorkspaceDomainRepository",
            "WorkspaceInvitationRepo",
            "WorkspaceRepository",
            "WorkspaceUserRepository",
        ),
        "identity",
    ),
    **dict.fromkeys(
        (
            "AllowedOriginsRepository",
            "CouponRepository",
            "FormPluginProviderRepository",
            "PriceSuggestionRepository",
            "UserFeedbackRepo",
        ),
        "refdata",
    ),
}

#: Mongo collection -> the repository group whose flags move it. Matches the
#: ``group=`` of the routed repository serving it (a test keeps them in step);
#: collections without a repository yet sit with their nearest relatives. The
#: migration CLI's ``--group`` selects by this map.
COLLECTION_GROUPS = {
    # identity
    "workspaces": "identity",
    "workspace_users": "identity",
    "workspace_invites": "identity",
    "workspace_api_keys": "identity",
    "workspace_domains": "identity",
    "sso_connections": "identity",
    "sso_used_states": "identity",
    "scim_directories": "identity",
    "scim_users": "identity",
    "scim_groups": "identity",
    "scim_group_members": "identity",
    "scim_events": "identity",
    "blacklisted_refresh_tokens": "identity",
    "sessions": "identity",
    "user_tags": "identity",
    # forms
    "forms": "forms",
    "form_versions": "forms",
    "form_templates": "forms",
    "workspace_forms": "forms",
    "form_imports": "forms",
    "media_libraries": "forms",
    "workspace_consent": "forms",
    "scheduler_form_configs": "forms",
    # responses
    "form_responses": "responses",
    "responses_deletion_requests": "responses",
    "workspace_responder": "responses",
    "workspace_tags": "responses",
    "responder_group": "responses",
    "responder_group_form": "responses",
    "responder_group_member": "responses",
    # actions
    "actions": "actions",
    "workspace_actions": "actions",
    # ai
    "ai_preference_memories": "ai",
    "form_ai_sessions": "ai",
    "form_ai_insights": "ai",
    "workspace_ai_profiles": "ai",
    "mcp_audit_logs": "ai",
    "create_form_prompts": "ai",
    "api_idempotency_keys": "ai",
    # analytics
    "form_flow_events": "analytics",
    "rate_limit_counters": "analytics",
    # refdata
    "allowed_origins": "refdata",
    "forms_plugin_configs": "refdata",
    "coupon_codes": "refdata",
    "price_suggestion": "refdata",
    "user_feedback": "refdata",
}


def _listed(names: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    return " and ".join(n for n in (", ".join(names[:-1]), names[-1]) if n)


def load_backend_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """The backend's flags (:func:`common.db.load_flags`: the jobs backends).
    A per-group flag left from the cutover that names another store for a group
    of :data:`POSTGRES_ONLY_GROUPS` (``DB_READ_SOURCE__refdata=mongo``,
    ``DB_WRITE_MODE__ai=dual`` ...) refuses the start: the store it asks for
    is no longer there. A service-wide ``DB_READ_SOURCE`` / ``DB_WRITE_MODE``
    means nothing to the backend and is ignored."""
    refuse_stale_store_flags(
        env,
        POSTGRES_ONLY_GROUPS,
        what=f"the {_listed(POSTGRES_ONLY_GROUPS)} groups are served from "
        "Postgres only since 4.1 and have no Mongo store any more.",
        service_wide=False,
    )
    return load_flags(env)
