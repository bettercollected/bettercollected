"""Enterprise SSO through Ory Polis (spike, see docs/sso-spike.md).

Polis turns a customer's SAML (or OIDC) IdP into a plain OAuth 2.0
authorization-code flow. We stay the identity owner: Polis only tells us who
the IdP vouched for; users, tokens and workspace membership remain ours.

Flow: ``get_basic_auth_url`` resolves the tenant (a workspace id) from the
work email's domain and sends the browser to Polis's ``/api/oauth/authorize``
with PKCE. Polis runs SAML with the IdP and redirects to the backend's
``/auth/sso/callback`` with a code, which lands in ``basic_auth_callback``:
exchange it at ``/api/oauth/token``, read ``/api/oauth/userinfo``, and accept
the email only when its domain belongs to that tenant.
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

from auth.app.exceptions import HTTPException
from auth.app.services.base_auth_provider import BaseAuthProvider
from auth.app.services.platform_admins import roles_for
from auth.app.services.provider_sign_in import account_for_provider_sign_in
from auth.config import settings
from common.configs.crypto import Crypto
from common.models.user import User

crypto: Crypto = Crypto(settings.AUTH_AES_HEX_KEY)

PKCE_VERIFIER_STATE_KEY = "pkce_code_verifier"
SSO_WORKSPACE_KEY = "sso_workspace_id"


def _error(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message, **extra})


def email_domain(email: Optional[str]) -> str:
    email = (email or "").strip().lower()
    local, at, domain = email.rpartition("@")
    return domain if at and local and domain else ""


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _client_id(tenant: str, product: str) -> str:
    # Polis convention for "no registered client": the tenant and product
    # encoded in the client_id (it parses this exact shape).
    return f"tenant={tenant}&product={product}"


class SSOAuthProvider(BaseAuthProvider):
    def __init__(self, sso_settings=None, transport: httpx.AsyncBaseTransport = None):
        self._settings = sso_settings
        self._transport = transport

    @property
    def sso(self):
        return self._settings or settings.sso_settings

    def _require_enabled(self):
        if not self.sso.ENABLED or not self.sso.polis_url or not self.sso.REDIRECT_URI:
            raise _error(404, "sso_disabled", "SSO sign-in is not enabled.")

    async def get_basic_auth_url(self, client_referer_url: str, *args, **kwargs) -> str:
        self._require_enabled()
        email = (kwargs.get("login_hint") or "").strip().lower()
        domain = email_domain(email)
        tenant = self.sso.tenant_for_domain(domain) if domain else None
        if not tenant:
            raise _error(
                404,
                "sso_not_configured",
                "Single sign-on isn't set up for this email domain.",
            )
        product = self.sso.POLIS_PRODUCT
        code_verifier = secrets.token_urlsafe(64)
        state = crypto.encrypt(
            json.dumps(
                {
                    "client_referer_url": client_referer_url,
                    "creator": kwargs.get("creator", False),
                    "prospective_pro_user": kwargs.get("prospective_pro_user", False),
                    "tenant": tenant,
                    "product": product,
                    "issued_at": int(time.time()),
                    PKCE_VERIFIER_STATE_KEY: code_verifier,
                }
            )
        )
        params = {
            "response_type": "code",
            "client_id": _client_id(tenant, product),
            "redirect_uri": self.sso.REDIRECT_URI,
            "state": state,
            "code_challenge": pkce_challenge(code_verifier),
            "code_challenge_method": "S256",
            "login_hint": email,
        }
        return f"{self.sso.polis_url}/api/oauth/authorize?{urlencode(params)}"

    def _read_state(self, state: str) -> Dict[str, Any]:
        try:
            state_json = json.loads(crypto.decrypt(state))
            code_verifier = state_json.pop(PKCE_VERIFIER_STATE_KEY)
            tenant = state_json["tenant"]
            product = state_json["product"]
            issued_at = int(state_json["issued_at"])
            if not all(
                isinstance(v, str) and v for v in (code_verifier, tenant, product)
            ):
                raise ValueError("incomplete state")
        except (InvalidToken, KeyError, TypeError, ValueError, AttributeError):
            raise _error(400, "sso_bad_state", "Bad request")
        if time.time() - issued_at > self.sso.STATE_MAX_AGE_SECONDS:
            raise _error(
                400,
                "sso_expired",
                "The sign-in took too long. Please try again.",
                client_referer_url=state_json.get("client_referer_url"),
            )
        state_json[PKCE_VERIFIER_STATE_KEY] = code_verifier
        return state_json

    async def _polis_profile(
        self, code: str, code_verifier: str, tenant: str, product: str
    ):
        base = self.sso.polis_internal_url
        async with httpx.AsyncClient(
            transport=self._transport, timeout=self.sso.HTTP_TIMEOUT_SECONDS
        ) as client:
            token_response = await client.post(
                f"{base}/api/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": _client_id(tenant, product),
                    "client_secret": self.sso.POLIS_CLIENT_SECRET or "",
                    "code": code,
                    "redirect_uri": self.sso.REDIRECT_URI,
                    "code_verifier": code_verifier,
                },
            )
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

    async def basic_auth_callback(self, code: str, state: str, *args, **kwargs):
        self._require_enabled()
        state_json = self._read_state(state)
        code_verifier = state_json.pop(PKCE_VERIFIER_STATE_KEY)
        tenant, product = state_json["tenant"], state_json["product"]
        referer = state_json.get("client_referer_url")
        try:
            profile = await self._polis_profile(code, code_verifier, tenant, product)
        except httpx.HTTPError as e:
            loguru.logger.error("Polis unreachable: {}", type(e).__name__)
            profile = None
        if not profile:
            raise _error(
                401,
                "sso_failed",
                "Single sign-on failed. Please try again.",
                client_referer_url=referer,
            )
        requested = profile.get("requested") or {}
        # The code must have been issued for the tenant this sign-in started
        # with, never another connection's.
        if requested.get("tenant") != tenant or requested.get("product") != product:
            raise _error(
                403,
                "sso_tenant_mismatch",
                "Single sign-on failed.",
                client_referer_url=referer,
            )
        email = (profile.get("email") or "").strip().lower()
        # The IdP asserted this address. We only believe it for domains the
        # tenant owns; anything else is refused outright, so an SSO login can
        # never reach an account outside the tenant's domains.
        if not email or email_domain(email) not in self.sso.domains_for_tenant(tenant):
            raise _error(
                403,
                "sso_email_domain_not_allowed",
                "Your identity provider signed you in with an email address this "
                "workspace's single sign-on doesn't cover.",
                client_referer_url=referer,
            )
        # Only now does the email count as verified (#758): the IdP vouched
        # for it and the tenant owns its domain.
        user_document = await account_for_provider_sign_in(
            _user_repository(),
            "sso",
            email,
            True,
            creator=state_json.get("creator", False),
            first_name=profile.get("firstName") or None,
            last_name=profile.get("lastName") or None,
        )
        user = User(
            id=str(user_document.id),
            sub=user_document.email,
            roles=roles_for(user_document.email, user_document.roles, True),
            plan=user_document.plan,
            email_verified=True,
        )
        state_json["user"] = user.dict()
        state_json[SSO_WORKSPACE_KEY] = tenant
        return state_json


def _user_repository():
    from auth.app.container import container

    return container.user_repository()
