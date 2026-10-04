"""Signing in with single sign-on, and testing a connection (docs/sso.md).

The backend decides *who may* sign in with SSO; the auth service runs the
OAuth code flow with Polis and owns the accounts:

1. ``login_url``: the work email's domain must be a verified SSO domain of a
   workspace (``WorkspaceDomainService.sso_domain_claim``) that has an enabled
   connection and is available. Auth builds the Polis authorize URL (PKCE,
   encrypted state carrying the tenant, the connection and our context).
2. ``complete``: auth exchanges the code, checks the code was issued for the
   tenant and connection the sign-in started with, and hands back the email
   the IdP asserted (not yet an account). Here, before any account exists:
   the connection is still enabled, the workspace still available, the
   email's domain is a verified SSO domain *of this workspace*, and an
   account that is not a member yet fits under the seat cap. Only then does
   auth find or create the account, the member joins with the workspace's
   default role (never downgrading an existing membership), and the caller
   starts a session.

Errors go back to the login page as ``?sso_error=<code>``, codes from
``SSO_ERROR_CODES`` only. A "Test connection" sign-in (``purpose=test``)
runs the same checks for an admin, records the outcome on the connection and
never signs anyone in or creates an account.
"""

import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from beanie import PydanticObjectId
from common.exceptions.http import HTTPException as CommonHTTPException
from common.models.user import User
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.sso_connection_repository import SsoConnectionRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.domains.names import domain_of
from backend.app.services.internal_auth import auth_service_headers
from backend.app.services.session_service import SSO_METHOD
from backend.app.services.sso.connection_service import SsoConnectionService
from backend.app.services.sso.policy import default_sso_role
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.app.services.workspace_user_service import (
    SeatLimitReached,
    WorkspaceUserService,
)
from backend.config import settings

PURPOSE_LOGIN = "login"
PURPOSE_TEST = "test"

# Everything the login page may be told; anything else becomes sso_failed.
SSO_ERROR_CODES = frozenset(
    {
        "sso_disabled",
        "sso_not_configured",
        "sso_failed",
        "sso_expired",
        "sso_bad_state",
        "sso_tenant_mismatch",
        "sso_email_domain_not_allowed",
        "sso_workspace_unavailable",
        "sso_seat_limit",
        "sso_account_conflict",
        "sso_test_not_allowed",
    }
)


class SsoRefused(Exception):
    """A refused SSO step: send the browser to ``redirect``."""

    def __init__(self, code: str, redirect: str):
        super().__init__(code)
        self.code = code
        self.redirect = redirect


@dataclass
class SsoSignIn:
    user: User
    redirect: str


@dataclass
class SsoTestDone:
    redirect: str


def _error_code(error: Exception) -> str:
    content = getattr(error, "content", None)
    code = content.get("code") if isinstance(content, dict) else None
    return code if code in SSO_ERROR_CODES else "sso_failed"


def _error_context(error: Exception) -> Dict[str, Any]:
    content = getattr(error, "content", None)
    context = content.get("context") if isinstance(content, dict) else None
    return context if isinstance(context, dict) else {}


def with_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key
    ]
    query.append((key, value))
    return urlunsplit(parts._replace(query=urlencode(query)))


class SsoLoginService:
    def __init__(
        self,
        http_client,
        connection_repo: SsoConnectionRepository,
        connection_service: SsoConnectionService,
        domain_service: WorkspaceDomainService,
        workspace_repo: WorkspaceRepository,
        workspace_user_service: WorkspaceUserService,
        authorization_service: AuthorizationService,
        auth_service,
    ):
        self._http = http_client
        self._connections = connection_repo
        self._connection_service = connection_service
        self._domains = domain_service
        self._workspace_repo = workspace_repo
        self._members = workspace_user_service
        self._authorization = authorization_service
        self._auth_service = auth_service

    # -- redirects ------------------------------------------------------------
    async def _safe(self, url: Optional[str], default_path: str) -> str:
        """``url`` if it is on one of this instance's origins (the
        login-redirect allow-list), else the client URL's ``default_path``."""
        return await self._auth_service.safe_login_redirect(url, default_path)

    async def _login_error(self, referer: Optional[str], code: str) -> str:
        page = await self._safe(referer, "/login")
        return with_param(
            page, "sso_error", code if code in SSO_ERROR_CODES else "sso_failed"
        )

    async def _test_result(self, context: Dict[str, Any], result: str) -> str:
        workspace = None
        try:
            workspace = await self._workspace_repo.find_by_id(
                PydanticObjectId(context.get("ws"))
            )
        except Exception:  # noqa: BLE001 — a bad id: no such workspace
            workspace = None
        base = await self._safe(context.get("r"), "/")
        if workspace is not None:
            base = urljoin(base, f"/{workspace.workspace_name}/dashboard/sso")
        return with_param(base, "sso_test", result)

    # -- start ----------------------------------------------------------------
    async def login_url(self, email: str, referer: Optional[str]) -> str:
        """Where to send the browser for ``email``: the identity provider, or
        back to the login page with ``sso_error``."""
        referer = await self._safe(referer, "/login")
        if not settings.sso.is_configured:
            raise SsoRefused(
                "sso_disabled", await self._login_error(referer, "sso_disabled")
            )
        email = (email or "").strip().lower()
        claim = await self._domains.sso_domain_claim(email) if "@" in email else None
        connection = (
            await self._connections.find_enabled(claim.workspace_id) if claim else None
        )
        if connection is None:
            raise SsoRefused(
                "sso_not_configured",
                await self._login_error(referer, "sso_not_configured"),
            )
        workspace = await self._workspace_repo.find_by_id(claim.workspace_id)
        if workspace is None or workspace.disabled:
            raise SsoRefused(
                "sso_workspace_unavailable",
                await self._login_error(referer, "sso_workspace_unavailable"),
            )
        context = {
            "p": PURPOSE_LOGIN,
            "ws": str(workspace.id),
            "c": str(connection.id),
            "r": referer,
        }
        return await self._authorize_url(connection, email, context, referer)

    async def test_url(
        self,
        workspace_id: PydanticObjectId,
        connection_id: str,
        user: User,
        referer: Optional[str],
    ) -> str:
        """Start a "Test connection" sign-in (security.manage). Works for a
        disabled connection too: testing comes before enabling."""
        connection = await self._connection_service.connection_for_test(
            workspace_id, connection_id, user
        )
        referer = await self._safe(referer, "/")
        context = {
            "p": PURPOSE_TEST,
            "ws": str(workspace_id),
            "c": str(connection.id),
            "u": str(user.id),
            "r": referer,
        }
        return await self._authorize_url(connection, None, context, referer)

    async def _authorize_url(self, connection, email, context, referer) -> str:
        params = {
            "tenant": connection.polis_tenant,
            "client_id": connection.polis_client_id,
            "context": json.dumps(context, separators=(",", ":")),
        }
        if email:
            params["login_hint"] = email
        try:
            reply = await self._http.get(
                settings.auth_settings.BASE_URL + "/auth/sso/authorize",
                params=params,
                headers=auth_service_headers(),
            )
        except (HTTPException, CommonHTTPException) as error:
            code = _error_code(error)
            if context.get("p") == PURPOSE_TEST:
                raise SsoRefused(code, await self._test_result(context, code))
            raise SsoRefused(code, await self._login_error(referer, code))
        return reply.get("auth_url")

    # -- callback -------------------------------------------------------------
    async def complete(
        self,
        code: Optional[str],
        state: Optional[str],
        idp_error: bool,
        signed_in: Optional[User],
    ):
        """Finish a sign-in or a test. Returns SsoSignIn (start a session) or
        SsoTestDone; raises SsoRefused."""
        if not state:
            raise SsoRefused("sso_failed", await self._login_error(None, "sso_failed"))
        params = {"state": state}
        if code and not idp_error:
            params["code"] = code
        else:
            params["idp_error"] = "true"
        try:
            profile = await self._http.get(
                settings.auth_settings.BASE_URL + "/auth/sso/callback",
                params=params,
                headers=auth_service_headers(),
                timeout=60,
            )
        except (HTTPException, CommonHTTPException) as error:
            error_code = _error_code(error)
            context = _error_context(error)
            if context.get("p") == PURPOSE_TEST:
                await self._record_test_failure(context, error_code)
                raise SsoRefused(
                    error_code, await self._test_result(context, error_code)
                )
            raise SsoRefused(
                error_code, await self._login_error(context.get("r"), error_code)
            )

        context = profile.get("context") if isinstance(profile, dict) else None
        context = context if isinstance(context, dict) else {}
        if context.get("p") == PURPOSE_TEST:
            return await self._finish_test(profile, context, signed_in)
        return await self._finish_login(profile, context)

    async def _checked(self, profile: dict, context: dict):
        """The connection, workspace and domain checks a sign-in and a test
        share. Returns (connection, workspace) or raises a code."""
        workspace_id = context.get("ws")
        if not workspace_id or profile.get("tenant") != workspace_id:
            raise _Code("sso_tenant_mismatch")
        connection = await self._connections.get(context.get("c"))
        if (
            connection is None
            or str(connection.workspace_id) != workspace_id
            or connection.polis_client_id != profile.get("polis_client_id")
        ):
            raise _Code("sso_tenant_mismatch")
        workspace = await self._workspace_repo.find_by_id(
            PydanticObjectId(workspace_id)
        )
        if workspace is None or workspace.disabled:
            raise _Code("sso_workspace_unavailable")
        email = (profile.get("email") or "").strip().lower()
        claim = await self._domains.sso_domain_claim(email) if email else None
        if claim is None or str(claim.workspace_id) != workspace_id:
            # the IdP vouched for an address outside this workspace's verified
            # domains (unverified, lost, or another workspace's): refused
            # before any account is touched
            raise _Code("sso_email_domain_not_allowed")
        return connection, workspace, email

    async def _finish_login(self, profile: dict, context: dict) -> SsoSignIn:
        referer = context.get("r")
        try:
            connection, workspace, email = await self._checked(profile, context)
            if not connection.is_enabled:
                raise _Code("sso_not_configured")
            if profile.get("account_conflict"):
                raise _Code("sso_account_conflict")
            existing_id = profile.get("existing_user_id")
            member = (
                await self._members.find_member(workspace.id, existing_id)
                if existing_id
                else None
            )
            # the seat cap is checked before an account exists (shortcut 2)
            if member is None and not await self._members.has_free_seat(workspace.id):
                raise _Code("sso_seat_limit")
        except _Code as refused:
            logger.info(
                "SSO sign-in refused ({}) for workspace {}",
                refused.code,
                context.get("ws"),
            )
            raise SsoRefused(
                refused.code, await self._login_error(referer, refused.code)
            )

        try:
            reply = await self._http.post(
                settings.auth_settings.BASE_URL + "/auth/sso/account",
                json={"assertion": profile.get("assertion")},
                headers=auth_service_headers(),
            )
        except (HTTPException, CommonHTTPException) as error:
            code = _error_code(error)
            raise SsoRefused(code, await self._login_error(referer, code))
        user = User(**{**reply, "auth_method": SSO_METHOD, "email_verified": True})
        try:
            await self._members.add_sso_member(
                workspace.id, user, default_sso_role(workspace)
            )
        except SeatLimitReached:
            # filled up between the look and the write: the account exists,
            # but no membership and no session
            raise SsoRefused(
                "sso_seat_limit", await self._login_error(referer, "sso_seat_limit")
            )
        logger.info(
            "SSO sign-in of user {} to workspace {} (domain {})",
            user.id,
            workspace.id,
            domain_of(email),
        )
        page = await self._safe(referer, "/login")
        return SsoSignIn(
            user=user,
            redirect=urljoin(page, f"/{workspace.workspace_name}/dashboard/forms"),
        )

    async def _finish_test(
        self, profile: dict, context: dict, signed_in: Optional[User]
    ) -> SsoTestDone:
        # only the admin who started the test, still allowed to manage SSO,
        # records its outcome
        if (
            signed_in is None
            or str(signed_in.id) != context.get("u")
            or not await self._authorization.has_permission(
                signed_in, Permission.SECURITY_MANAGE, context.get("ws")
            )
        ):
            raise SsoRefused(
                "sso_test_not_allowed",
                await self._test_result(context, "sso_test_not_allowed"),
            )
        try:
            connection, _workspace, _email = await self._checked(profile, context)
        except _Code as refused:
            await self._record_test_failure(context, refused.code)
            raise SsoRefused(
                refused.code, await self._test_result(context, refused.code)
            )
        await self._connection_service.record_test(connection, signed_in.id, None)
        return SsoTestDone(redirect=await self._test_result(context, "ok"))

    async def _record_test_failure(self, context: dict, code: str) -> None:
        connection = await self._connections.get(context.get("c"))
        if connection is not None and str(connection.workspace_id) == context.get("ws"):
            await self._connection_service.record_test(
                connection, context.get("u") or "", code
            )


class _Code(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
