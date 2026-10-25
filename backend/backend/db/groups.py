"""Repository groups and the order they may leave Mongo in.

A group's Mongo repositories may ``$lookup`` into another group's collections.
Such a join finds nothing once the joined group stops writing Mongo, so while
the joining group still reads from Mongo, the joined groups must keep writing
it (``dual`` / ``postgres_primary_dual``). ``load_flags`` enforces the map at
boot; the Postgres twins compose over routed repositories instead of joining,
so a group served from Postgres frees the groups it used to join into.
"""

import os
from dataclasses import replace
from typing import Mapping, Sequence

from common.db.flags import (
    OVERRIDE_SEP,
    READ_KEY,
    WRITE_KEY,
    DbFlags,
    FlagError,
    ReadSource,
    WriteMode,
    load_flags,
)
from common.db.groups import BACKEND_GROUPS

GROUPS = BACKEND_GROUPS

#: Groups served from Postgres only: their repositories have no Mongo side and
#: no routing any more. Their collections are read only by the import from 4.0
#: (``python -m backend.migrate``).
POSTGRES_ONLY_GROUPS = ("refdata", "analytics", "ai", "actions")

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
}


def _listed(names: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    return " and ".join(n for n in (", ".join(names[:-1]), names[-1]) if n)


def load_backend_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """The backend's flags (:func:`common.db.load_flags`), with every group of
    :data:`POSTGRES_ONLY_GROUPS` on Postgres whatever the defaults say. A
    per-group flag left from the cutover that names another store for one
    of them (``DB_READ_SOURCE__refdata=mongo``, ``DB_WRITE_MODE__ai=dual``
    ...) refuses the start: the store it asks for is no longer there."""
    prefixes = tuple(base + OVERRIDE_SEP for base in (READ_KEY, WRITE_KEY))

    def pinned(key: str) -> bool:
        """A per-group flag of a group served from Postgres only."""
        return (
            key.startswith(prefixes)
            and key.split(OVERRIDE_SEP, 1)[1].lower() in POSTGRES_ONLY_GROUPS
        )

    stale = sorted(
        f"{key}={value!r}"
        for key, value in env.items()
        if pinned(key) and value.strip().lower() not in ("", "postgres")
    )
    if stale:
        raise FlagError(
            f"{', '.join(stale)}: the {_listed(POSTGRES_ONLY_GROUPS)} groups "
            "are served from Postgres only since 4.1 and have no Mongo store any "
            "more. Remove these settings (or set them to postgres) and restart."
        )
    # what is left of them (postgres, or empty) is implied: left out, so that
    # e.g. a remaining DB_READ_SOURCE__actions=postgres is not checked against
    # the default write mode
    flags = load_flags(
        {k: v for k, v in env.items() if not pinned(k)}, mongo_joins=MONGO_JOINS
    )
    return replace(
        flags,
        read_overrides={
            **flags.read_overrides,
            **{g: ReadSource.POSTGRES for g in POSTGRES_ONLY_GROUPS},
        },
        write_overrides={
            **flags.write_overrides,
            **{g: WriteMode.POSTGRES for g in POSTGRES_ONLY_GROUPS},
        },
    )
