from typing import List, Optional

from common.records import Record, RecordId

# a request by an owner's email-code session that the SSO requirement would
# otherwise have refused: one entry per request
SSO_BREAK_GLASS_REQUEST = "sso_break_glass_request"
# an owner signed in with an email code on an address the workspace requires
# single sign-on for (the session may never reach a workspace route)
SSO_BREAK_GLASS_SIGN_IN = "sso_break_glass_sign_in"


# a staff member changed answers of a response (docs/response-revisions.md):
# who, when, the form and response and the history entry's number, no value
RESPONSE_STAFF_EDIT = "response_staff_edit"
# a staff member opened the previous values of one history entry
RESPONSE_REVISION_READ = "response_revision_read"
# (written by ``services/response_revisions/audit.py``; grouped here so that
# ``ALL_KINDS`` holds every kind there is)
RESPONSE_REVISION_EVENTS = (RESPONSE_STAFF_EDIT, RESPONSE_REVISION_READ)

# second-factor (authenticator app) events of an account (docs/totp.md): ids
# only, never a code, a secret or an address. ``workspace_id`` is NO_WORKSPACE
# when no workspace is involved.
TOTP_ENROLLED = "totp_enrolled"
TOTP_REMOVED = "totp_removed"
TOTP_RESET = "totp_reset"
TOTP_RECOVERY_USED = "totp_recovery_used"
TOTP_RECOVERY_REGENERATED = "totp_recovery_regenerated"
TOTP_LOCKED = "totp_locked"
TOTP_POLICY_CHANGED = "totp_policy_changed"
TOTP_EVENTS = (
    TOTP_ENROLLED,
    TOTP_REMOVED,
    TOTP_RESET,
    TOTP_RECOVERY_USED,
    TOTP_RECOVERY_REGENERATED,
    TOTP_LOCKED,
    TOTP_POLICY_CHANGED,
)
# form-level access events (``FORM_ACCESS_ENABLED``): grants, teams and a
# form's access mode. Ids and enum values only, never a team name, a form title
# or an address.
ACCESS_GRANT_ADDED = "access_grant_added"
ACCESS_GRANT_CHANGED = "access_grant_changed"
ACCESS_GRANT_REMOVED = "access_grant_removed"
ACCESS_MODE_CHANGED = "access_mode_changed"
TEAM_CREATED = "team_created"
TEAM_RENAMED = "team_renamed"
TEAM_DELETED = "team_deleted"
TEAM_MEMBER_ADDED = "team_member_added"
TEAM_MEMBER_REMOVED = "team_member_removed"
# a directory group linked to or unlinked from a team
TEAM_LINKED = "team_linked"
# removing a member deleted N grants and team memberships
ACCESS_MEMBER_PURGED = "access_member_purged"
# removing a member handed a form they created to the workspace's billing owner
# (form_id, target_user_id = who it was, to_user_id = who it is now)
FORM_CREATOR_REASSIGNED = "form_creator_reassigned"
ACCESS_EVENTS = (
    ACCESS_GRANT_ADDED,
    ACCESS_GRANT_CHANGED,
    ACCESS_GRANT_REMOVED,
    ACCESS_MODE_CHANGED,
    TEAM_CREATED,
    TEAM_RENAMED,
    TEAM_DELETED,
    TEAM_MEMBER_ADDED,
    TEAM_MEMBER_REMOVED,
    TEAM_LINKED,
    ACCESS_MEMBER_PURGED,
    FORM_CREATOR_REASSIGNED,
)
# workspace members (members.manage): ids and enum values only, never an
# address. An invitation has no account yet, so it is named by its id.
MEMBER_INVITED = "member_invited"
MEMBER_INVITATION_REVOKED = "member_invitation_revoked"
MEMBER_INVITATION_ACCEPTED = "member_invitation_accepted"
MEMBER_REMOVED = "member_removed"
MEMBER_ROLE_CHANGED = "member_role_changed"
# forms and responses: the form, how many responses, never a title or an answer
FORM_PUBLISHED = "form_published"
FORM_DELETED = "form_deleted"
RESPONSES_DELETED = "responses_deleted"
# data left through an export, a bulk read or a response PDF: a pointer to the
# export's own audit row (``export_id``), with its channel, format and rows
RESPONSE_EXPORT = "response_export"
MEMBER_FORM_EVENTS = (
    MEMBER_INVITED,
    MEMBER_INVITATION_REVOKED,
    MEMBER_INVITATION_ACCEPTED,
    MEMBER_REMOVED,
    MEMBER_ROLE_CHANGED,
    FORM_PUBLISHED,
    FORM_DELETED,
    RESPONSES_DELETED,
    RESPONSE_EXPORT,
)
# API key lifecycle events: ids and enum values only, never a key's name, prefix
# or token, nor a form title.
# an API key was revoked (key_id, reason): because its creator left (removed
# from the workspace, their account deleted or the directory deprovisioned them;
# target_user_id = the creator), or by an admin
API_KEY_REVOKED = "api_key_revoked"
# API_KEY_ROLES_ENABLED: a key created, its role or form scope changed, a form
# added to or removed from its list
API_KEY_CREATED = "api_key_created"
API_KEY_ROLE_CHANGED = "api_key_role_changed"
API_KEY_SCOPE_CHANGED = "api_key_scope_changed"
API_KEY_FORM_ADDED = "api_key_form_added"
API_KEY_FORM_REMOVED = "api_key_form_removed"
API_KEY_EVENTS = (
    API_KEY_REVOKED,
    API_KEY_CREATED,
    API_KEY_ROLE_CHANGED,
    API_KEY_SCOPE_CHANGED,
    API_KEY_FORM_ADDED,
    API_KEY_FORM_REMOVED,
)
# the reasons of API_KEY_REVOKED
REVOKED_MEMBER_REMOVED = "member_removed"
REVOKED_ACCOUNT_DELETED = "account_deleted"
REVOKED_SCIM_DEPROVISIONED = "scim_deprovisioned"
# a form's structure left a workspace for another one, or came from another one
# (FORM_PROMOTION_ENABLED): ids and counts only, never a title, a name or a text of
# the form. FORM_COPIED_OUT is written in the source workspace (form_id = the
# source form, target_workspace_id, target_form_id when it updates one; the file
# download names no target and has export_channel "file"); FORM_PROMOTED in the target workspace (form_id = the
# target form, source_workspace_id, source_form_id; ``count`` = what was adjusted
# to fit). Both are stored before the change.
FORM_COPIED_OUT = "form_copied_out"
FORM_PROMOTED = "form_promoted"
PROMOTION_EVENTS = (FORM_COPIED_OUT, FORM_PROMOTED)
# an admin revoked the key on the API keys page
REVOKED_BY_ADMIN = "admin"
# the workspace was deleted (every key of it, whoever made it)
REVOKED_WORKSPACE_DELETED = "workspace_deleted"
# ``key_role`` / ``key_role_before`` of a key that has no role of its own: it acts
# as its creator
KEY_ROLE_AS_CREATOR = "creator"
# workspace security settings (``security.manage``): single sign-on, the verified
# email domains, directory sync (SCIM), the AI consent and the custom domain.
# Ids and enum values only, never a name, a hostname, an address, a URL, a token
# or a secret. A flag is only ever ``required`` / ``enabled`` (the new value).
SSO_CONNECTION_CREATED = "sso_connection_created"
SSO_CONNECTION_ENABLED = "sso_connection_enabled"
SSO_CONNECTION_DISABLED = "sso_connection_disabled"
SSO_CONNECTION_DELETED = "sso_connection_deleted"
# "Require single sign-on" turned on or off (``required``)
SSO_REQUIRED_CHANGED = "sso_required_changed"
# the role members signing in through SSO get (``role``, ``previous_role``)
SSO_DEFAULT_ROLE_CHANGED = "sso_default_role_changed"
# a verified email domain claimed, verified or released (``domain_id``)
DOMAIN_CLAIMED = "domain_claimed"
DOMAIN_VERIFIED = "domain_verified"
DOMAIN_REMOVED = "domain_removed"
# directory sync: the token is created with the directory, replaced (the old one
# stops working) or revoked with it (``directory_id``, ``directory_type``)
SCIM_TOKEN_CREATED = "scim_token_created"
SCIM_TOKEN_ROTATED = "scim_token_rotated"
SCIM_TOKEN_REVOKED = "scim_token_revoked"
# a directory group mapped to a role or unmapped (``directory_group_id``,
# ``role``, ``previous_role``)
SCIM_GROUP_ROLE_CHANGED = "scim_group_role_changed"
# AI features turned on or off for the workspace (``enabled``, ``provider``)
AI_CONSENT_CHANGED = "ai_consent_changed"
# the workspace's own hostname set, replaced or removed (no hostname stored)
CUSTOM_DOMAIN_CHANGED = "custom_domain_changed"
CUSTOM_DOMAIN_REMOVED = "custom_domain_removed"
SETTINGS_EVENTS = (
    SSO_CONNECTION_CREATED,
    SSO_CONNECTION_ENABLED,
    SSO_CONNECTION_DISABLED,
    SSO_CONNECTION_DELETED,
    SSO_REQUIRED_CHANGED,
    SSO_DEFAULT_ROLE_CHANGED,
    DOMAIN_CLAIMED,
    DOMAIN_VERIFIED,
    DOMAIN_REMOVED,
    SCIM_TOKEN_CREATED,
    SCIM_TOKEN_ROTATED,
    SCIM_TOKEN_REVOKED,
    SCIM_GROUP_ROLE_CHANGED,
    AI_CONSENT_CHANGED,
    CUSTOM_DOMAIN_CHANGED,
    CUSTOM_DOMAIN_REMOVED,
)
# a form's integrations (email actions and the case-system registration): the
# action, service or form, never an address, a URL, a template, a name or a
# secret. ``changed`` lists which parts of the configuration changed, by a fixed
# vocabulary (``AUTOMATION_PARTS``), never their old or new content.
EMAIL_ACTION_CREATED = "email_action_created"
EMAIL_ACTION_UPDATED = "email_action_updated"
EMAIL_ACTION_ENABLED = "email_action_enabled"
EMAIL_ACTION_DISABLED = "email_action_disabled"
EMAIL_ACTION_DELETED = "email_action_deleted"
REGISTRATION_SERVICE_CREATED = "registration_service_created"
REGISTRATION_SERVICE_UPDATED = "registration_service_updated"
REGISTRATION_SERVICE_DELETED = "registration_service_deleted"
FORM_REGISTRATION_ENABLED = "form_registration_enabled"
FORM_REGISTRATION_DISABLED = "form_registration_disabled"
FORM_REGISTRATION_CHANGED = "form_registration_changed"
AUTOMATION_EVENTS = (
    EMAIL_ACTION_CREATED,
    EMAIL_ACTION_UPDATED,
    EMAIL_ACTION_ENABLED,
    EMAIL_ACTION_DISABLED,
    EMAIL_ACTION_DELETED,
    REGISTRATION_SERVICE_CREATED,
    REGISTRATION_SERVICE_UPDATED,
    REGISTRATION_SERVICE_DELETED,
    FORM_REGISTRATION_ENABLED,
    FORM_REGISTRATION_DISABLED,
    FORM_REGISTRATION_CHANGED,
)
# the parts a ``changed`` list may name (anything else is dropped at write time)
AUTOMATION_PARTS = (
    "name",
    "en",
    "nl",
    "fields",
    "team_recipients",
    "respondent_copy",
    "condition",
    "all_questions",
    "base_url",
    "objecttypes_base_url",
    "auth",
    "secret",
    "organisation_name",
    "service",
    "path",
    "variables",
    "object_type",
    "reference_path",
)
# the audit log itself: a staff member took the log (or part of it) out as a file.
# Written before the file starts: ``export_format`` (``csv`` / ``json``), ``count``
# (how many entries the file holds), ``export_filters`` (the NAMES of the filters
# that narrowed it, from ``AUDIT_EXPORT_FILTERS``, never their values) and the
# form's id when the export was of one form.
AUDIT_LOG_EXPORTED = "audit_log_exported"
AUDIT_LOG_EVENTS = (AUDIT_LOG_EXPORTED,)
AUDIT_EXPORT_FILTERS = (
    "area",
    "event",
    "actor",
    "target",
    "involving",
    "form",
    "from",
    "to",
)
# the reserved workspace id of an event that belongs to no workspace
NO_WORKSPACE = "000000000000000000000000"

# the events of the single sign-on break-glass log (what its page lists)
SSO_EVENTS = (SSO_BREAK_GLASS_REQUEST, SSO_BREAK_GLASS_SIGN_IN)

# every kind of event there is: the union of the ``*_EVENTS`` groups above (the
# response history's two kinds have a writer of their own but are in it too). The
# writers in ``services/form_access/audit.py`` accept exactly these. A new group
# of kinds is added here (``tests/app/audit_events/test_all_kinds.py`` fails until
# it is).
ALL_KINDS = (
    TOTP_EVENTS
    + ACCESS_EVENTS
    + MEMBER_FORM_EVENTS
    + API_KEY_EVENTS
    + PROMOTION_EVENTS
    + SETTINGS_EVENTS
    + AUTOMATION_EVENTS
    + SSO_EVENTS
    + RESPONSE_REVISION_EVENTS
    + AUDIT_LOG_EVENTS
)


class WorkspaceAuditEventDocument(Record):
    """A security event of a workspace (docs/sso.md, "Owner break-glass is
    audited"): ids only, never an address or a name. The time is
    ``created_at``."""

    workspace_id: RecordId
    user_id: str
    session_id: Optional[str] = None
    event: str
    # request entries: the HTTP method and the route's path *template*
    # (``/workspaces/{workspace_id}/forms``), never a query, a body or a
    # concrete id from the path
    method: Optional[str] = None
    path: Optional[str] = None
    # response entries (RESPONSE_*): ids and the history entry's number only
    form_id: Optional[str] = None
    response_id: Optional[str] = None
    revision: Optional[int] = None
    # TOTP_POLICY_CHANGED: what the workspace rule was set to
    required: Optional[bool] = None
    # TOTP_* entries made by someone else (an owner or the platform admin
    # resetting a member's factor): the account it was done to
    target_user_id: Optional[str] = None
    # FORM_CREATOR_REASSIGNED: the person the form was handed to
    to_user_id: Optional[str] = None
    # ACCESS_* / TEAM_* entries (form-level access): the team, the role and
    # export flag of a grant, a form's new access mode, a number of rows
    group_id: Optional[str] = None
    grant_role: Optional[str] = None
    grant_export: Optional[bool] = None
    access_mode: Optional[str] = None
    count: Optional[int] = None
    # TEAM_LINKED: the directory group (our id for it), and whether it was
    # linked to the team (``group_id``) or unlinked from it
    scim_group_id: Optional[str] = None
    linked: Optional[bool] = None
    # MEMBER_*: the invitation, the role it gives or the member now holds (an
    # enum value of WorkspaceRoles) and, for a change, the one it replaced
    invitation_id: Optional[str] = None
    role: Optional[str] = None
    previous_role: Optional[str] = None
    # RESPONSE_EXPORT: the id of the export's row (``response_exports``), its
    # channel and format (enum values); the number of rows is ``count``
    export_id: Optional[str] = None
    export_channel: Optional[str] = None
    export_format: Optional[str] = None
    # API_KEY_* entries: the key (its id only), why it was revoked, its role (and
    # the one before), its form scope and whether the change gave the key more
    # access
    key_id: Optional[str] = None
    reason: Optional[str] = None
    key_role: Optional[str] = None
    key_role_before: Optional[str] = None
    form_scope: Optional[str] = None
    widened: Optional[bool] = None
    # SETTINGS_EVENTS: the SSO connection (id and type, ``saml`` / ``oidc``),
    # the verified-domain claim, the SCIM directory (id and type), the new value
    # of an on/off setting and the AI provider's id (enum values, no names)
    connection_id: Optional[str] = None
    connection_type: Optional[str] = None
    domain_id: Optional[str] = None
    directory_id: Optional[str] = None
    directory_type: Optional[str] = None
    # SCIM_GROUP_ROLE_CHANGED: the directory's group (not a team: ``group_id``
    # is a team's)
    directory_group_id: Optional[str] = None
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    # AUTOMATION_EVENTS: the email action or case-system service (ids), and
    # which parts of the configuration changed (``AUTOMATION_PARTS``)
    action_id: Optional[str] = None
    service_id: Optional[str] = None
    changed: Optional[List[str]] = None
    # FORM_COPIED_OUT / FORM_PROMOTED: the other side of the copy (ids only)
    source_workspace_id: Optional[str] = None
    source_form_id: Optional[str] = None
    target_workspace_id: Optional[str] = None
    target_form_id: Optional[str] = None
    # AUDIT_LOG_EXPORTED: the names of the filters the export applied (a fixed
    # vocabulary, ``AUDIT_EXPORT_FILTERS``; never their values)
    export_filters: Optional[List[str]] = None

    class Settings:
        name = "workspace_audit_events"
