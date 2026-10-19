"""Repository groups and the order they may leave Mongo in.

A group's Mongo repositories may ``$lookup`` into another group's collections.
Such a join finds nothing once the joined group stops writing Mongo, so while
the joining group still reads from Mongo, the joined groups must keep writing
it (``dual`` / ``postgres_primary_dual``). ``load_flags`` enforces the map at
boot; the Postgres twins compose over routed repositories instead of joining,
so a group served from Postgres frees the groups it used to join into.
"""

from common.db.groups import BACKEND_GROUPS

GROUPS = BACKEND_GROUPS

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

MONGO_JOINS = {
    # FormResponseRepository / DeletionRequestsRepository → forms, workspace_forms
    "responses": ("forms",),
    # FormTemplateRepository.get_templates_with_creator → workspaces
    "forms": ("identity",),
    # WorkspaceRepository.get_workspace_with_action_by_id → workspace_actions
    "identity": ("actions",),
}
