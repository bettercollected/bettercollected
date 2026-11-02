"""The event kinds the audit log lists, by area: the one list the API validates
a filter against, and the list a reader never goes beyond.

Every kind constant of ``schemas/workspace_audit_event.py`` is in exactly one
area here, or in ``ACCOUNT_LEVEL`` (a test compares the two, so a kind added to
the schema cannot ship unlisted). A kind in ``ACCOUNT_LEVEL`` belongs to a
person, not to a workspace, and is never returned by the workspace feed, even
if a row carried the workspace's id.
"""

from typing import Dict, FrozenSet, Optional, Tuple

from backend.app.schemas import workspace_audit_event as E

AREA_ACCESS = "access"
AREA_MEMBERS = "members"
AREA_FORMS = "forms"
AREA_RESPONSES = "responses"
AREA_API_KEYS = "api_keys"
AREA_SECURITY = "security"
AREA_INTEGRATIONS = "integrations"

# area -> its kinds, in the order the page's filter offers them
AREAS: Dict[str, Tuple[str, ...]] = {
    # who may open which form: grants, a form's access mode, teams
    AREA_ACCESS: (
        E.ACCESS_GRANT_ADDED,
        E.ACCESS_GRANT_CHANGED,
        E.ACCESS_GRANT_REMOVED,
        E.ACCESS_MODE_CHANGED,
        E.TEAM_CREATED,
        E.TEAM_RENAMED,
        E.TEAM_DELETED,
        E.TEAM_MEMBER_ADDED,
        E.TEAM_MEMBER_REMOVED,
        E.TEAM_LINKED,
        E.ACCESS_MEMBER_PURGED,
    ),
    AREA_MEMBERS: (
        E.MEMBER_INVITED,
        E.MEMBER_INVITATION_REVOKED,
        E.MEMBER_INVITATION_ACCEPTED,
        E.MEMBER_REMOVED,
        E.MEMBER_ROLE_CHANGED,
    ),
    AREA_FORMS: (
        E.FORM_PUBLISHED,
        E.FORM_DELETED,
        E.FORM_CREATOR_REASSIGNED,
        # a form's structure copied to another workspace, or from one
        E.FORM_COPIED_OUT,
        E.FORM_PROMOTED,
    ),
    # answers read, changed, deleted or taken out (never the answers)
    AREA_RESPONSES: (
        E.RESPONSE_STAFF_EDIT,
        E.RESPONSE_REVISION_READ,
        E.RESPONSES_DELETED,
        E.RESPONSE_EXPORT,
    ),
    AREA_API_KEYS: E.API_KEY_EVENTS,
    # single sign-on, break-glass use, the workspace's authenticator rule and the
    # rest of its security settings
    AREA_SECURITY: (
        E.SSO_BREAK_GLASS_REQUEST,
        E.SSO_BREAK_GLASS_SIGN_IN,
        E.TOTP_POLICY_CHANGED,
        E.TOTP_RESET,
        # single sign-on, verified domains, directory sync, AI consent, custom
        # domain
        *E.SETTINGS_EVENTS,
        # the log itself taken out as a file
        *E.AUDIT_LOG_EVENTS,
    ),
    # email actions and case-system services and registrations
    AREA_INTEGRATIONS: E.AUTOMATION_EVENTS,
}

# the second-factor events of one account (written with ``NO_WORKSPACE``): shown
# on the person's own account page one day, never in a workspace's feed
ACCOUNT_LEVEL: FrozenSet[str] = frozenset(
    {
        E.TOTP_ENROLLED,
        E.TOTP_REMOVED,
        E.TOTP_RECOVERY_USED,
        E.TOTP_RECOVERY_REGENERATED,
        E.TOTP_LOCKED,
    }
)

LISTED: FrozenSet[str] = frozenset(kind for kinds in AREAS.values() for kind in kinds)

_AREA_OF = {kind: area for area, kinds in AREAS.items() for kind in kinds}


def area_of(event: str) -> Optional[str]:
    """The area of a listed kind (None for any other)."""
    return _AREA_OF.get(event)


def kinds_of(areas=None, events=None) -> Tuple[str, ...]:
    """The kinds a request asks for, as one list: those of the given areas and
    the given kinds together, or every listed kind when it names none. Only
    listed kinds are ever returned. Raises ``ValueError`` for an area or a kind
    that is not in the catalogue."""
    chosen = []
    for area in areas or ():
        if area not in AREAS:
            raise ValueError(area)
        chosen.extend(AREAS[area])
    for event in events or ():
        if event not in LISTED:
            raise ValueError(event)
        chosen.append(event)
    if not (areas or events):
        return tuple(sorted(LISTED))
    return tuple(dict.fromkeys(chosen))
