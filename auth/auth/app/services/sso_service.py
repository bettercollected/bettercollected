"""Enterprise single sign-on through Ory Polis (docs/sso.md).

Polis turns a customer's SAML or OIDC identity provider into a plain OAuth 2.0
authorization-code flow. We stay the identity owner: Polis only tells us who
the IdP vouched for; accounts, tokens and memberships remain ours.

The backend decides who may use SSO (verified domains, the workspace's
enabled connection, seats) and calls this service, which is internal-only:

1. ``authorize_url``: the Polis authorize URL for the workspace (tenant) and
   connection (Polis clientID) the backend chose, with PKCE and an encrypted
   state holding the tenant, the connection, the verifier, the time and the
   backend's context.
2. ``callback``: decrypt the state (at most ``STATE_MAX_AGE_SECONDS`` old),
   exchange the code at ``/api/oauth/token`` with the verifier, read
   ``/api/oauth/userinfo`` and check Polis issued it for the same tenant,
   product and connection. Returns the asserted (lower-cased) email, which
   account holds it, and a short-lived encrypted assertion. **No account is
   created here**: the backend first checks the domain and the seat cap.
3. ``account``: for an assertion this service issued (at most
   ``ASSERTION_MAX_AGE_SECONDS`` old), find or create the account through
   ``account_for_provider_sign_in``. The email counts as verified (the IdP
   vouched for it, and the backend checked its domain is verified by the
   workspace), but the session never gets the platform-admin role.

Emails are matched case-insensitively at this boundary: an existing
``Bob@Example.com`` account is the one ``bob@example.com`` signs in to.
"""

import base64
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
import loguru
from cryptography.fernet import InvalidToken
from email_validator import EmailNotValidError, validate_email

from auth.app.exceptions import HTTPException
from common.enums.roles import Roles
from auth.app.services.platform_admins import roles_for
from auth.app.services.provider_sign_in import account_for_provider_sign_in
from auth.config import settings
from common.configs.crypto import Crypto
from common.models.user import User

PROVIDER = "sso"
AUTH_METHOD = "sso"
MAX_CONTEXT_LENGTH = 2048

crypto: Crypto = Crypto(settings.AUTH_AES_HEX_KEY)


def _error(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message, **extra})


def normalized_email(email: Optional[str]) -> str:
    """Lower-cased, trimmed; empty when it is not an email address."""
    value = (email or "").strip().lower()
    if not value or len(value) > 320:
        return ""
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        return ""
    return value


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class SsoService:
    def __init__(
        self,
        user_repository,
        sso_settings=None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._users = user_repository
        self._settings = sso_settings
        self._transport = transport

    @property
    def sso(self):
        return self._settings or settings.sso_settings

    def _require_enabled(self):
        if not self.sso.ENABLED or not self.sso.polis_url or not self.sso.REDIRECT_URI:
            raise _error(404, "sso_disabled", "Single sign-on is not enabled.")

    # -- 1. start -------------------------------------------------------------
    def authorize_url(
        self,
        tenant: str,
        client_id: str,
        context: Optional[str] = None,
        login_hint: Optional[str] = None,
    ) -> str:
        self._require_enabled()
        if not tenant or not client_id:
            raise _error(400, "sso_not_configured", "No connection to sign in with.")
        context_json: Dict[str, Any] = {}
        if context:
            if len(context) > MAX_CONTEXT_LENGTH:
                raise _error(400, "sso_failed", "Bad request")
            try:
                context_json = json.loads(context)
            except ValueError:
                raise _error(400, "sso_failed", "Bad request")
            if not isinstance(context_json, dict):
                raise _error(400, "sso_failed", "Bad request")
        code_verifier = secrets.token_urlsafe(64)
        state = crypto.encrypt(
            json.dumps(
                {
                    "tenant": tenant,
                    "product": self.sso.POLIS_PRODUCT,
                    "client_id": client_id,
                    "issued_at": int(time.time()),
                    "verifier": code_verifier,
                    "context": context_json,
                }
            )
        )
        params = {
            "response_type": "code",
            # the connection's own clientID: Polis signs in with exactly this
            # connection and records its tenant (checked at the callback)
            "client_id": client_id,
            "redirect_uri": self.sso.REDIRECT_URI,
            "state": state,
            "code_challenge": pkce_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
        hint = normalized_email(login_hint)
        if hint:
            params["login_hint"] = hint
        return f"{self.sso.polis_url}/api/oauth/authorize?{urlencode(params)}"

    # -- 2. callback ----------------------------------------------------------
    def _read_state(self, state: str) -> Dict[str, Any]:
        try:
            state_json = json.loads(crypto.decrypt(state))
            for key in ("tenant", "product", "client_id", "verifier"):
                if not isinstance(state_json[key], str) or not state_json[key]:
                    raise ValueError("incomplete state")
            issued_at = int(state_json["issued_at"])
            if not isinstance(state_json.get("context", {}), dict):
                raise ValueError("bad context")
        except (InvalidToken, KeyError, TypeError, ValueError, AttributeError):
            raise _error(400, "sso_bad_state", "Bad request")
        if time.time() - issued_at > self.sso.STATE_MAX_AGE_SECONDS:
            raise _error(
                400,
                "sso_expired",
                "The sign-in took too long. Please try again.",
                context=state_json.get("context") or {},
            )
        return state_json

    async def _polis_profile(self, code: str, state_json: Dict[str, Any]):
        base = self.sso.polis_internal_url
        form = {
            "grant_type": "authorization_code",
            "client_id": state_json["client_id"],
            "code": code,
            "redirect_uri": self.sso.REDIRECT_URI,
            "code_verifier": state_json["verifier"],
        }
        if self.sso.POLIS_CLIENT_SECRET:
            form["client_secret"] = self.sso.POLIS_CLIENT_SECRET
        async with httpx.AsyncClient(
            transport=self._transport, timeout=self.sso.HTTP_TIMEOUT_SECONDS
        ) as client:
            token_response = await client.post(f"{base}/api/oauth/token", data=form)
            if token_response.status_code != 200:
                loguru.logger.warning(
                    "Polis token exchange failed: HTTP {}", token_response.status_code
                )
                return None
            access_token = token_response.json().get("access_token")
            if not access_token:
                return None
            userinfo = await client.get(
                f"{base}/api/oauth/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo.status_code != 200:
                loguru.logger.warning(
                    "Polis userinfo failed: HTTP {}", userinfo.status_code
                )
                return None
            return userinfo.json()

    async def callback(
        self, code: Optional[str], state: str, idp_error: bool = False
    ) -> Dict[str, Any]:
        self._require_enabled()
        state_json = self._read_state(state)
        context = state_json.get("context") or {}
        if idp_error or not code:
            # Polis reported a failure at the IdP (?error=...): no code to
            # exchange, but the backend learns where to send the browser
            raise _error(
                401,
                "sso_failed",
                "Single sign-on failed. Please try again.",
                context=context,
            )
        try:
            profile = await self._polis_profile(code, state_json)
        except (httpx.HTTPError, ValueError) as error:
            loguru.logger.error("Polis unreachable: {}", type(error).__name__)
            profile = None
        if not isinstance(profile, dict):
            raise _error(
                401,
                "sso_failed",
                "Single sign-on failed. Please try again.",
                context=context,
            )
        requested = profile.get("requested") or {}
        # The code must have been issued for the tenant and the connection
        # this sign-in started with, never another one.
        if (
            requested.get("tenant") != state_json["tenant"]
            or requested.get("product") != state_json["product"]
            or requested.get("client_id") != state_json["client_id"]
        ):
            raise _error(
                403, "sso_tenant_mismatch", "Single sign-on failed.", context=context
            )
        email = normalized_email(profile.get("email"))
        if not email:
            raise _error(
                403,
                "sso_email_domain_not_allowed",
                "Your identity provider did not send a usable email address.",
                context=context,
            )
        first_name = (profile.get("firstName") or "").strip()[:100] or None
        last_name = (profile.get("lastName") or "").strip()[:100] or None
        existing, conflict = await self._existing_account(email)
        assertion = crypto.encrypt(
            json.dumps(
                {
                    "email": email,
                    "tenant": state_json["tenant"],
                    "first_name": first_name,
                    "last_name": last_name,
                    "issued_at": int(time.time()),
                    "purpose": "sso_account",
                }
            )
        )
        return {
            "tenant": state_json["tenant"],
            "polis_client_id": state_json["client_id"],
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "existing_user_id": str(existing.id) if existing else None,
            "account_conflict": conflict,
            "context": context,
            "assertion": assertion,
        }

    async def _existing_account(self, email: str):
        """(account, conflict): the account for ``email`` ignoring case. An
        exact (lower-case) match wins; otherwise a single case-insensitive
        match; several case variants and no exact one is a conflict."""
        exact = await self._users.get_user_by_email(email)
        if exact is not None:
            return exact, False
        matches = await self._users.find_users_by_email_ci(email)
        if len(matches) == 1:
            return matches[0], False
        return None, len(matches) > 1

    # -- 3. account -----------------------------------------------------------
    async def account(self, assertion: str) -> User:
        self._require_enabled()
        try:
            claim = json.loads(crypto.decrypt(assertion))
            if claim.get("purpose") != "sso_account":
                raise ValueError("not an SSO assertion")
            email = normalized_email(claim["email"])
            issued_at = int(claim["issued_at"])
            if not email:
                raise ValueError("no email")
        except (InvalidToken, KeyError, TypeError, ValueError, AttributeError):
            raise _error(400, "sso_bad_state", "Bad request")
        if time.time() - issued_at > self.sso.ASSERTION_MAX_AGE_SECONDS:
            raise _error(
                400, "sso_expired", "The sign-in took too long. Please try again."
            )
        existing, conflict = await self._existing_account(email)
        if conflict:
            raise _error(
                409, "sso_account_conflict", "Several accounts use this email."
            )
        # The IdP asserted it and the backend checked its domain is verified
        # by the workspace: only now does the email count as verified (#758).
        user_document = await account_for_provider_sign_in(
            self._users,
            PROVIDER,
            existing.email if existing else email,
            True,
            creator=True,
            first_name=claim.get("first_name"),
            last_name=claim.get("last_name"),
        )
        return self._sso_user(user_document)

    # -- 4. directory sync (SCIM) ---------------------------------------------
    async def directory_account(
        self,
        email: str,
        create: bool,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """The account of a user the workspace's SCIM directory provisions:
        ``{"user": User | None, "conflict": bool}``. The backend calls this
        only for an address on one of the workspace's verified domains, after
        checking the seat cap (docs/sso.md, "Directory sync"). With ``create``
        false it only looks the account up (deprovisioning); with ``create``
        true a missing account is created like a first SSO sign-in (email
        verified, never the platform-admin role)."""
        self._require_enabled()
        email = normalized_email(email)
        if not email:
            raise _error(422, "invalid_email", "Not an email address.")
        existing, conflict = await self._existing_account(email)
        if conflict:
            return {"user": None, "conflict": True}
        if existing is None and not create:
            return {"user": None, "conflict": False}
        user_document = existing
        if user_document is None:
            user_document = await account_for_provider_sign_in(
                self._users,
                PROVIDER,
                email,
                True,
                creator=True,
                first_name=(first_name or "").strip()[:100] or None,
                last_name=(last_name or "").strip()[:100] or None,
            )
        return {"user": self._sso_user(user_document), "conflict": False}

    @staticmethod
    def _sso_user(user_document) -> User:
        return User(
            id=str(user_document.id),
            sub=user_document.email,
            # An identity provider never grants the platform-admin role: not
            # from PLATFORM_ADMIN_EMAILS (verified=False) and not one stored
            # on the account either (the backend strips it on refresh too).
            roles=[
                role
                for role in roles_for(
                    user_document.email, user_document.roles, verified=False
                )
                if role != Roles.ADMIN.value
            ],
            plan=user_document.plan,
            email_verified=True,
            auth_method=AUTH_METHOD,
        )
