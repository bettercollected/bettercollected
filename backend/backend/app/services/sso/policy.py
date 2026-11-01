"""Single sign-on policy: SSO-required domains and the JIT default role.

A workspace that requires SSO (``sso_required``) refuses every other sign-in
(email code, Google) for addresses on its SSO domains, the verified domains
single sign-on applies to (``WorkspaceDomainService.sso_domains``). It only
takes effect while the instance has SSO switched on, the workspace is
available and it has an enabled connection: if any of those is missing the
members could not sign in with SSO either, so nothing is refused.

**Break-glass:** the workspace's owners (the billing owner and every member
with role OWNER) may still sign in with an email code, so a broken identity
provider cannot lock everyone out of the workspace. Google sign-in stays
refused for owners too: the code proves the owner's mailbox; a Google
account on the same address is a second path we don't need.

**Bound to the workspace:** an SSO session carries the workspace whose
identity provider signed it in (``sso_workspace_id``) and meets only *that*
workspace's requirement. A verified domain that moves to another workspace
cannot carry existing SSO sessions over to it: they are refused there (at once
and at their refresh) and sign in again. A session made before the binding
existed has none and does not meet the requirement either.

**Respondents:** the requirement covers the dashboard and the workspace's
own forms. On *another* workspace's forms such an address may still verify
itself with an email code, but only into a respondent-scoped session (no
workspace permissions, no creator or admin role).

**Refresh:** while the requirement holds, a session for an address on those
domains that did not sign in with SSO ends at its next refresh, member or
not, except the owners' email-code sessions and respondent-scoped ones.

**Every request:** the same rule is also applied when a request is authorised
for the workspace (``blocks_session``, called by ``AuthorizationService``),
so a session that does not meet the requirement is refused at once and not
only at its next refresh. API keys are machine credentials issued inside the
workspace and are not subject to it (the owners are shown the keys that
predate the requirement). Each time an owner's email-code session is let in by
break-glass, an audit row is written for the request (session, user, method
and route template; ids only), and a log line once per session and hour. See
docs/sso.md.
"""

import asyncio
import base64
import collections
import datetime as dt
import time
from http import HTTPStatus
from typing import Deque, Dict, List, Optional, Tuple

from common.records import RecordId
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import (
    WorkspaceRoles,
    canonical_role,
    is_owner_membership,
)
from backend.app.repositories.postgres.identity import (
    PostgresSsoConnectionRepository,
    PostgresWorkspaceRepository,
)
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_audit_event import (
    SSO_BREAK_GLASS_REQUEST,
    SSO_BREAK_GLASS_SIGN_IN,
    WorkspaceAuditEventDocument,
)
from backend.app.services.domains.names import display_domain, domain_of
from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.request_context import current_request, method_and_template
from backend.app.services.session_service import (
    OTP_METHOD,
    RESPONDENT_SCOPE,
    SSO_METHOD,
)
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.config import settings

SSO_REQUIRED = "sso_required"

# The sign-in method of an API key's acting user (``api_access.acting_user``).
API_KEY_METHOD = "api_key"

# How long a workspace's answer to "does this address's domain require SSO
# here" (a verified domain claim plus an enabled connection) is reused by the
# per-request check. Whether the workspace requires SSO at all is never
# cached: it comes from the workspace row the authorisation already reads. So
# switching the requirement on or off takes effect on the next request; only
# a domain claim or connection that changed in the last few seconds can be
# seen late (and a changed one is only ever acted on a little late).
REQUIREMENT_CACHE_SECONDS = 30.0
REQUIREMENT_CACHE_MAX = 2048

# The break-glass log line (not the audit rows, which are one per request) is
# written once per session and workspace per hour, so a busy dashboard does not
# flood the log.
BREAK_GLASS_AUDIT_SECONDS = 3600.0
BREAK_GLASS_AUDIT_MAX = 4096

# The break-glass write is a single INSERT; if the database cannot take it within
# this, the request goes on and the entry is queued for the next write.
AUDIT_WRITE_TIMEOUT_SECONDS = 2.0
AUDIT_PENDING_MAX = 500
# The audit list: page size and the most a client may ask for.
AUDIT_PAGE_SIZE = 20
AUDIT_PAGE_MAX = 100

# How long the workspace audit entries are kept: a year, then the daily purge
# (``sso_audit_purge``) deletes them; they go with the workspace too.
AUDIT_RETENTION = dt.timedelta(days=365)

# The role a first SSO sign-in gets unless the workspace chose another.
# The accepted design's default (docs/enterprise-access-model.md): Viewer.
DEFAULT_SSO_ROLE = WorkspaceRoles.VIEWER

# What an owner may pick as the SSO default, highest first. Owner, Admin and
# Privacy officer are granted by hand, never by an identity provider.
SSO_ASSIGNABLE_ROLES = (
    WorkspaceRoles.EDITOR,
    WorkspaceRoles.REVIEWER,
    WorkspaceRoles.VIEWER,
)


def sso_session_meets(
    method: Optional[str],
    sso_workspace_id: Optional[str],
    workspace_id,
    sso_connection_id: Optional[str] = None,
    enabled_connection_id=None,
) -> bool:
    """An SSO session meets the requirement of the workspace whose identity
    provider signed it in, and of no other, and only while that identity
    provider is still the workspace's enabled connection
    (``enabled_connection_id``; None: the workspace has none enabled, so
    nothing is required and nothing is refused). A session without that
    binding (made before it existed) meets none."""
    if not (
        method == SSO_METHOD
        and sso_workspace_id
        and workspace_id is not None
        and str(sso_workspace_id) == str(workspace_id)
    ):
        return False
    return enabled_connection_id is None or str(sso_connection_id or "") == str(
        enabled_connection_id
    )


def session_exempt(
    method: Optional[str],
    scope: Optional[str],
    is_owner: bool = False,
    sso_workspace_id: Optional[str] = None,
    workspace_id=None,
    sso_connection_id: Optional[str] = None,
    enabled_connection_id=None,
) -> bool:
    """The one rule of who meets (or is outside) a workspace's single
    sign-on requirement, by how the session was made: SSO sessions signed in
    through this workspace (``sso_workspace_id`` is ``workspace_id``), API
    keys (machine credentials), respondent-scoped sessions, and an owner's
    email-code session (break-glass). Used by the refresh, the selection
    screen and the per-request check, so they cannot drift."""
    if method == API_KEY_METHOD or scope == RESPONDENT_SCOPE:
        return True
    if sso_session_meets(
        method,
        sso_workspace_id,
        workspace_id,
        sso_connection_id,
        enabled_connection_id,
    ):
        return True
    return method == OTP_METHOD and is_owner


def encode_audit_cursor(entry: WorkspaceAuditEventDocument) -> str:
    """An opaque keyset cursor: where the next page starts (this entry's time
    and id: nothing secret, and nothing it could be abused with)."""
    raw = f"{entry.created_at.isoformat()}|{entry.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_audit_cursor(cursor: str):
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        stamp, _, entry_id = raw.partition("|")
        at = dt.datetime.fromisoformat(stamp)
        if at.tzinfo is None:
            at = at.replace(tzinfo=dt.timezone.utc)
        if not entry_id or len(entry_id) > 64:
            raise ValueError("id")
        return at, entry_id
    except (ValueError, UnicodeError) as error:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            {"code": "invalid_cursor", "message": "That page of the audit log is not valid."},
        ) from error


def assignable_sso_roles() -> List[str]:
    return [role.value for role in SSO_ASSIGNABLE_ROLES]


def default_sso_role(workspace: Optional[WorkspaceDocument]) -> WorkspaceRoles:
    """The workspace's configured default role (as the API speaks it), if it
    is (still) one SSO may give. A stored ``COLLABORATOR`` (the default
    before the new roles) is Editor and is kept, not migrated."""
    role = canonical_role(getattr(workspace, "sso_default_role", None))
    return role if role in SSO_ASSIGNABLE_ROLES else DEFAULT_SSO_ROLE


def sso_required_error(domain: str) -> HTTPException:
    return HTTPException(
        HTTPStatus.FORBIDDEN,
        {
            "code": SSO_REQUIRED,
            "message": (
                f"Your organisation requires single sign-on for {display_domain(domain)} "
                "addresses. Use “Sign in with SSO” instead."
            ),
        },
    )


class SsoPolicyService:
    def __init__(
        self,
        workspace_repo: PostgresWorkspaceRepository,
        domain_service: WorkspaceDomainService,
        connection_repo: PostgresSsoConnectionRepository,
        http_client=None,
        workspace_user_repo=None,
        audit_repo=None,
    ):
        # the workspace security events (owner break-glass), docs/sso.md
        self._audit = audit_repo
        self._workspace_repo = workspace_repo
        self._domains = domain_service
        self._connections = connection_repo
        self._http_client = http_client
        # the memberships: who the owners are (an enabled one each)
        self._workspace_users = workspace_user_repo
        # (workspace id, domain) -> (expires at, whether the domain requires
        # SSO there), per process; see REQUIREMENT_CACHE_SECONDS
        self._requirement_cache: Dict[Tuple[str, str], Tuple[float, bool]] = {}
        self._clock = time.monotonic
        # (workspace id, session) -> when its break-glass was last audited
        self._break_glass_seen: Dict[Tuple[str, str], float] = {}
        # audit entries a failed write did not store, retried with the next one
        self._audit_pending: Deque = collections.deque(maxlen=AUDIT_PENDING_MAX)
        # workspace id -> (expires at, id of its enabled connection or None)
        self._enabled_cache: Dict[str, Tuple[float, Optional[str]]] = {}

    async def requiring_workspace(self, email: str) -> Optional[WorkspaceDocument]:
        """The workspace whose SSO requirement covers ``email``, if any."""
        if not settings.sso.ENABLED:
            return None
        claim = await self._domains.sso_domain_claim(email)
        if claim is None:
            return None
        workspace = await self._workspace_repo.find_by_id(claim.workspace_id)
        if workspace is None or workspace.disabled or not workspace.sso_required:
            return None
        if await self._connections.find_enabled(workspace.id) is None:
            return None
        return workspace

    async def check_code_sign_in(
        self, email: str, user_id: Optional[str] = None
    ) -> None:
        """Refuse a full email-code sign-in (the dashboard) for an
        SSO-required address, unless it is one of the workspace's owners'
        (break-glass). ``user_id``: the account, once known."""
        await self.code_sign_in_scope(email, user_id=user_id)

    async def code_sign_in_scope(
        self,
        email: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[str]:
        """What an email-code sign-in for ``email`` may become: None for a
        full session, ``respondent`` for a session limited to answering the
        forms of ``workspace_id`` (another workspace than the one requiring
        SSO). Raises 403 ``sso_required`` otherwise. The workspace's owners
        keep full email-code sign-in (break-glass)."""
        workspace = await self.requiring_workspace(email)
        if workspace is None:
            return None
        if user_id is not None:
            is_owner = await self._is_owner(workspace, user_id)
        else:
            is_owner = await self._is_owner_email(workspace, email)
        if is_owner:
            logger.info(
                "SSO break-glass: an owner of workspace {} used an email code",
                workspace.id,
            )
            if user_id is not None:
                # the account is known (a verified code, not a request for one):
                # a session that never reaches a workspace route leaves a trace
                await self._record_audit(
                    SSO_BREAK_GLASS_SIGN_IN, workspace.id, user_id, None
                )
            return None
        if workspace_id and str(workspace_id) != str(workspace.id):
            return RESPONDENT_SCOPE
        raise sso_required_error(domain_of(email) or "")

    async def unmet_requirement(
        self,
        email: Optional[str],
        method: Optional[str],
        scope: Optional[str],
        user_id: Optional[str],
        sso_workspace_id: Optional[str] = None,
        sso_connection_id: Optional[str] = None,
    ) -> Optional[WorkspaceDocument]:
        """The workspace whose SSO requirement a session signed in with
        ``method`` (and ``scope``) does not meet, if any: the one requiring
        SSO for the address's domain, unless the session came from SSO, is
        respondent-scoped, or is an owner's email-code session
        (break-glass). The one rule behind ``session_must_end`` and the
        workspace selection screen."""
        if session_exempt(method, scope):
            return None
        workspace = await self.requiring_workspace(email or "")
        if workspace is None:
            return None
        if session_exempt(
            method,
            scope,
            is_owner=method == OTP_METHOD and await self._is_owner(workspace, user_id),
            sso_workspace_id=sso_workspace_id,
            workspace_id=workspace.id,
            sso_connection_id=sso_connection_id,
            enabled_connection_id=await self._enabled_connection_id(workspace.id),
        ):
            return None
        return workspace

    async def blocks_session(
        self,
        workspace: Optional[WorkspaceDocument],
        email: Optional[str],
        method: Optional[str],
        scope: Optional[str],
        is_owner: bool,
        sso_workspace_id: Optional[str] = None,
        sso_connection_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Whether a request to ``workspace`` by a session signed in with
        ``method`` must be refused for want of single sign-on: the rule of
        ``unmet_requirement`` (``is_owner``: an owner with an active
        membership, for the email-code break-glass), applied to the one
        workspace being accessed. An SSO session passes only when it was
        signed in through this workspace (``sso_workspace_id``). When an
        owner's email-code session is let in by break-glass, that is audited
        (``session_id`` and ``user_id`` name it; one row per request). The caller already holds the workspace row,
        so nothing is read unless the workspace requires SSO and the session
        could fall short; then at most the domain claim and the connection,
        reused for ``REQUIREMENT_CACHE_SECONDS``.

        Not covered, on purpose: API keys (machine credentials issued in the
        workspace; the key's creator still has to hold the permission),
        guests whose address is not on this workspace's SSO domains, and
        every workspace but the one that requires SSO."""
        if not settings.sso.ENABLED or workspace is None:
            return False
        if workspace.disabled or not workspace.sso_required:
            return False
        enabled = (
            await self._enabled_connection_id(workspace.id)
            if method == SSO_METHOD
            else None
        )
        if session_exempt(
            method,
            scope,
            sso_workspace_id=sso_workspace_id,
            workspace_id=workspace.id,
            sso_connection_id=sso_connection_id,
            enabled_connection_id=enabled,
        ):
            return False
        requires = await self._domain_requires_sso(workspace.id, email)
        if not requires:
            return False
        if session_exempt(method, scope, is_owner):
            await self._audit_break_glass(workspace.id, session_id, user_id)
            return False
        return True

    async def _audit_break_glass(self, workspace_id, session_id, user_id) -> None:
        """An owner's non-SSO session let into the SSO-required workspace:
        one audit row per request (however often the request is authorised):
        session, workspace, user, time, HTTP method and the route's path
        template. Plus one log line (ids only) per session, workspace and hour
        per process, for log-based alerting. Never raises, never refuses:
        break-glass is the incident path, so a failing audit is logged at ERROR
        and retried with the next write, not allowed to block access."""
        who = str(session_id or user_id or "")
        key = (str(workspace_id), who)
        now = self._clock()
        last = self._break_glass_seen.get(key)
        if last is None or now - last >= BREAK_GLASS_AUDIT_SECONDS:
            if len(self._break_glass_seen) >= BREAK_GLASS_AUDIT_MAX:
                self._break_glass_seen.clear()
            self._break_glass_seen[key] = now
            logger.bind(audit=True).warning(
                "AUDIT sso_break_glass workspace={} user={} session={}",
                workspace_id,
                user_id,
                session_id,
            )
        if not user_id:
            return
        context = current_request()
        if context is not None:
            if context.audited:
                return
            context.audited = True
        await self._record_audit(
            SSO_BREAK_GLASS_REQUEST, workspace_id, user_id, session_id, context
        )

    async def _record_audit(
        self,
        event: str,
        workspace_id,
        user_id,
        session_id: Optional[str],
        context=None,
    ) -> None:
        """Store one audit entry (ids and a route template only), after any
        entry an earlier write failed to store. One INSERT each, no read, under
        a short timeout. A failure is logged at ERROR and the entries not stored
        stay queued (bounded) for the next write; it never raises."""
        if self._audit is None:
            return
        method, path = method_and_template(context or current_request())
        document = WorkspaceAuditEventDocument(
            id=RecordId(),
            workspace_id=RecordId(str(workspace_id)),
            user_id=str(user_id),
            session_id=str(session_id) if session_id else None,
            event=event,
            method=method,
            path=path,
        )
        batch = [*self._audit_pending, document]
        self._audit_pending.clear()
        stored = 0
        try:
            async with asyncio.timeout(AUDIT_WRITE_TIMEOUT_SECONDS):
                for entry in batch:
                    await self._audit.record(entry)
                    stored += 1
        except Exception as error:  # noqa: BLE001 — fail open on the audit
            self._audit_pending.extend(batch[stored:])
            logger.bind(audit=True).error(
                "AUDIT sso_break_glass NOT STORED workspace={} user={} session={} "
                "event={} queued={} ({})",
                workspace_id,
                user_id,
                session_id,
                event,
                len(self._audit_pending),
                type(error).__name__,
            )

    async def audit_page(
        self, workspace_id, limit: int = AUDIT_PAGE_SIZE, cursor: Optional[str] = None
    ):
        """One page of the workspace's audit entries, newest first, and the
        cursor of the next page (None at the end). ``limit`` is capped at
        ``AUDIT_PAGE_MAX``; an unreadable cursor is 422."""
        if self._audit is None:
            return [], None
        limit = max(1, min(int(limit or AUDIT_PAGE_SIZE), AUDIT_PAGE_MAX))
        before = decode_audit_cursor(cursor) if cursor else None
        entries = await self._audit.page(workspace_id, limit + 1, before)
        more = len(entries) > limit
        entries = entries[:limit]
        return entries, (encode_audit_cursor(entries[-1]) if more and entries else None)

    async def delete_audit_for_workspaces(self, workspace_ids) -> int:
        if self._audit is None:
            return 0
        return await self._audit.delete_by_workspace_ids(workspace_ids)

    async def purge_audit(self, now: Optional[dt.datetime] = None) -> int:
        """The daily purge: entries older than ``AUDIT_RETENTION``."""
        if self._audit is None:
            return 0
        now = now or dt.datetime.now(dt.timezone.utc)
        return await self._audit.purge_before(now - AUDIT_RETENTION)

    async def session_would_be_blocked(
        self,
        workspace: WorkspaceDocument,
        user,
        is_owner: bool,
    ) -> bool:
        """Whether ``user``'s session would be refused by ``workspace`` once
        it requires single sign-on (it does not yet): the rule of
        ``blocks_session`` without looking at the requirement itself. For the
        warning shown to an owner who is about to switch it on."""
        if not settings.sso.ENABLED:
            return False
        if session_exempt(
            getattr(user, "auth_method", None),
            getattr(user, "session_scope", None),
            is_owner,
            sso_workspace_id=getattr(user, "sso_workspace_id", None),
            workspace_id=workspace.id,
            sso_connection_id=getattr(user, "sso_connection_id", None),
            enabled_connection_id=await self._enabled_connection_id(
                workspace.id, fresh=True
            ),
        ):
            return False
        domain = domain_of(getattr(user, "sub", "") or "")
        return domain is not None and domain in set(
            await self._domains.sso_domains(workspace.id)
        )

    async def _domain_requires_sso(self, workspace_id, email: Optional[str]) -> bool:
        """Whether ``email``'s domain is a verified SSO domain of the
        workspace and the workspace has an enabled connection."""
        domain = domain_of(email or "")
        if domain is None:
            return False
        key = (str(workspace_id), domain)
        now = self._clock()
        cached = self._requirement_cache.get(key)
        if cached is not None and cached[0] > now:
            return cached[1]
        claim = await self._domains.sso_domain_claim(domain)
        answer = (
            claim is not None
            and str(claim.workspace_id) == str(workspace_id)
            and await self._enabled_connection_id(workspace_id) is not None
        )
        if len(self._requirement_cache) >= REQUIREMENT_CACHE_MAX:
            self._requirement_cache.clear()
        self._requirement_cache[key] = (now + REQUIREMENT_CACHE_SECONDS, answer)
        return answer

    async def _enabled_connection_id(
        self, workspace_id, fresh: bool = False
    ) -> Optional[str]:
        """The id of the workspace's enabled connection, or None; reused for
        ``REQUIREMENT_CACHE_SECONDS`` unless ``fresh``."""
        key = str(workspace_id)
        now = self._clock()
        cached = self._enabled_cache.get(key)
        if not fresh and cached is not None and cached[0] > now:
            return cached[1]
        connection = await self._connections.find_enabled(RecordId(key))
        answer = str(connection.id) if connection is not None else None
        if len(self._enabled_cache) >= REQUIREMENT_CACHE_MAX:
            self._enabled_cache.clear()
        self._enabled_cache[key] = (now + REQUIREMENT_CACHE_SECONDS, answer)
        return answer

    async def sso_connection_replaced(self, session) -> bool:
        """Whether an SSO session signed in through a connection that is no
        longer its workspace's enabled one (the identity provider was
        replaced): it ends at its next refresh, requirement or not. A
        workspace without an enabled connection ends nothing."""
        workspace_id = getattr(session, "sso_workspace_id", None)
        if (
            not settings.sso.ENABLED
            or getattr(session, "method", None) != SSO_METHOD
            or not workspace_id
        ):
            return False
        enabled = await self._enabled_connection_id(workspace_id, fresh=True)
        return enabled is not None and enabled != str(
            getattr(session, "sso_connection_id", None) or ""
        )

    async def session_must_end(self, email: str, session, user_id: str) -> bool:
        """Whether a session has to end at refresh because its address's
        domain requires single sign-on: any session that did not sign in
        with SSO, except the owners' email-code sessions (break-glass) and
        respondent-scoped sessions."""
        workspace = await self.unmet_requirement(
            email,
            session.method,
            session.scope,
            user_id,
            sso_workspace_id=getattr(session, "sso_workspace_id", None),
            sso_connection_id=getattr(session, "sso_connection_id", None),
        )
        if workspace is None:
            return False
        logger.info(
            "SSO required in workspace {}: a {} session of user {} ended at refresh",
            workspace.id,
            session.method or "pre-SSO",
            user_id,
        )
        return True

    async def check_provider_sign_in(self, email: str) -> Optional[str]:
        """``sso_required`` when a Google (or other provider) sign-in for
        ``email`` must be refused, else None. No break-glass here."""
        if await self.requiring_workspace(email) is not None:
            return SSO_REQUIRED
        return None

    async def _owner_ids(self, workspace: WorkspaceDocument) -> List[str]:
        """The workspace's owners with an enabled membership: the billing
        owner and the members holding OWNER. A disabled membership (or none)
        is no owner here, the billing owner's included, as in
        ``authorization_service``."""
        if self._workspace_users is None:
            return [str(workspace.owner_id)] if workspace.owner_id else []
        owners = []
        for membership in await self._workspace_users.get_workspace_users(
            workspace_id=workspace.id
        ):
            if (
                not membership.disabled
                and is_owner_membership(workspace, membership)
                and str(membership.user_id) not in owners
            ):
                owners.append(str(membership.user_id))
        return owners

    async def _is_owner(self, workspace: WorkspaceDocument, user_id) -> bool:
        return user_id is not None and str(user_id) in await self._owner_ids(
            workspace
        )

    async def _is_owner_email(self, workspace: WorkspaceDocument, email: str) -> bool:
        owner_ids = await self._owner_ids(workspace)
        if not owner_ids or self._http_client is None:
            return False
        try:
            reply = await self._http_client.get(
                settings.auth_settings.BASE_URL + "/users",
                params={"user_ids": owner_ids},
                headers=auth_service_headers(),
            )
        except Exception as error:  # noqa: BLE001 — fail closed (code refused)
            logger.warning("SSO break-glass check failed: {}", type(error).__name__)
            return False
        for user in (reply or {}).get("users_info") or []:
            owner_email = (user.get("email") or "").strip().lower()
            if owner_email and owner_email == (email or "").strip().lower():
                return True
        return False

    async def sso_users_of(
        self, workspace_id: RecordId, user_ids: List[str]
    ) -> List[str]:
        """Of ``user_ids``, those whose email is on one of the workspace's SSO
        domains (to offer revoking their sessions)."""
        domains = set(await self._domains.sso_domains(workspace_id))
        if not domains or not user_ids or self._http_client is None:
            return []
        reply = await self._http_client.get(
            settings.auth_settings.BASE_URL + "/users",
            params={"user_ids": [str(u) for u in user_ids]},
            headers=auth_service_headers(),
        )
        found = []
        for user in (reply or {}).get("users_info") or []:
            if domain_of(user.get("email") or "") in domains:
                found.append(str(user.get("_id") or user.get("id")))
        return found
