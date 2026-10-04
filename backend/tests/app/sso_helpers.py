"""Stand-ins for single sign-on tests: Polis's admin API and the auth
service's SSO endpoints. Tests never call a real Polis or auth service, and
never resolve real names (the URL guard gets a fake resolver)."""

import datetime as dt
import json
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from beanie import PydanticObjectId
from common.exceptions.http import HTTPException as CommonHTTPException

from backend.app.container import container
from backend.app.schemas.sso_connection import (
    SsoConnectionDocument,
    SsoConnectionStatus,
    SsoConnectionType,
)
from backend.app.schemas.workspace_domain import DomainStatus, WorkspaceDomainDocument
from backend.app.services.sso.polis_client import PolisError
from backend.config import settings

POLIS_URL = "https://polis.test"
REDIRECT = "http://localhost:8000/api/v1/auth/sso/callback"
DOMAIN = "acme-sso.org"
LOGIN_PAGE = "http://localhost:3000/login"

PUBLIC_IP = "93.184.216.34"
SAML_XML = (
    '<?xml version="1.0"?><md:EntityDescriptor '
    'xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" '
    'entityID="https://idp.acme-sso.org/entity"><md:IDPSSODescriptor/>'
    "</md:EntityDescriptor>"
)


class FakePolisAdmin:
    def __init__(self):
        self.calls: List[tuple] = []
        self.connections: Dict[str, dict] = {}
        self.fail: Optional[PolisError] = None
        self._n = 0

    def _new(self, tenant, kind, **extra):
        if self.fail:
            raise self.fail
        self._n += 1
        client_id = f"polis-client-{self._n}"
        record = {"clientID": client_id, "clientSecret": "s", "tenant": tenant, **extra}
        self.connections[client_id] = record
        return record

    async def create_saml(self, tenant, name, raw_metadata=None, metadata_url=None):
        self.calls.append(
            ("create_saml", tenant, name, bool(raw_metadata), metadata_url)
        )
        return self._new(
            tenant, "saml", idpMetadata={"entityID": "https://idp.acme-sso.org/entity"}
        )

    async def create_oidc(self, tenant, name, discovery_url, client_id, client_secret):
        self.calls.append(("create_oidc", tenant, name, discovery_url, client_id))
        return self._new(tenant, "oidc")

    async def delete_connection(self, client_id):
        if self.fail:
            raise self.fail
        self.calls.append(("delete", client_id))
        self.connections.pop(client_id, None)

    async def delete_tenant(self, tenant):
        self.calls.append(("delete_tenant", tenant))


class FakeAuth:
    """The auth service as the backend's HttpClient sees it."""

    def __init__(self):
        self.accounts: Dict[str, dict] = {}
        self.idp_email = "jane@" + DOMAIN
        self.tenant_override: Optional[str] = None
        self.client_id_override: Optional[str] = None
        self.account_conflict = False
        self.calls: List[tuple] = []
        self.otp_user: Optional[dict] = None

    def add_account(self, email, user_id=None) -> dict:
        account = {
            "id": user_id or str(PydanticObjectId()),
            "sub": email,
            "email": email,
            "roles": ["FORM_RESPONDER", "FORM_CREATOR"],
            "plan": "FREE",
        }
        self.accounts[email.lower()] = account
        return account

    async def get(self, url, params=None, headers=None, timeout=None, **kwargs):
        params = params or {}
        path = urlsplit(url).path
        self.calls.append(("GET", path, dict(params)))
        if path.endswith("/auth/sso/authorize"):
            state = json.dumps(
                {
                    "tenant": params["tenant"],
                    "client_id": params["client_id"],
                    "context": json.loads(params["context"]),
                }
            )
            query = {"client_id": params["client_id"], "state": state}
            if params.get("login_hint"):
                query["login_hint"] = params["login_hint"]
            return {"auth_url": f"{POLIS_URL}/api/oauth/authorize?{urlencode(query)}"}
        if path.endswith("/auth/sso/callback"):
            try:
                state = json.loads(params["state"])
            except ValueError:
                raise CommonHTTPException(400, {"code": "sso_bad_state"})
            if params.get("idp_error"):
                raise CommonHTTPException(
                    401, {"code": "sso_failed", "context": state["context"]}
                )
            email = self.idp_email.lower()
            existing = self.accounts.get(email)
            return {
                "tenant": self.tenant_override or state["tenant"],
                "polis_client_id": self.client_id_override or state["client_id"],
                "email": email,
                "first_name": "Jane",
                "last_name": "Doe",
                "existing_user_id": existing["id"] if existing else None,
                "account_conflict": self.account_conflict,
                "context": state["context"],
                "assertion": "assert:" + email,
            }
        if path.endswith("/users"):
            ids = {str(i) for i in params.get("user_ids") or []}
            return {
                "users_info": [
                    {"_id": a["id"], "email": a["email"]}
                    for a in self.accounts.values()
                    if a["id"] in ids
                ]
            }
        if path.endswith("/auth/otp/send"):
            return {"message": "sent"}
        if path.endswith("/auth/otp/validate"):
            return {"user": self.otp_user}
        raise AssertionError(f"unexpected auth call {path}")

    async def post(self, url, json=None, headers=None, **kwargs):
        path = urlsplit(url).path
        self.calls.append(("POST", path, dict(json or {})))
        if path.endswith("/auth/sso/account"):
            email = json["assertion"].split(":", 1)[1]
            account = self.accounts.get(email) or self.add_account(email)
            return {
                **{k: account[k] for k in ("id", "sub", "roles", "plan")},
                "email_verified": True,
                "auth_method": "sso",
            }
        raise AssertionError(f"unexpected auth call {path}")

    def created_accounts(self) -> List[str]:
        return [c[2]["assertion"] for c in self.calls if c[1].endswith("/sso/account")]


async def public_resolver(host: str) -> List[str]:
    return [PUBLIC_IP]


@pytest.fixture
def sso_on(monkeypatch):
    sso = settings.sso
    for key, value in {
        "ENABLED": True,
        "POLIS_URL": POLIS_URL,
        "POLIS_INTERNAL_URL": "http://polis:5225",
        "POLIS_API_KEY": "test-api-key",
        "REDIRECT_URI": REDIRECT,
        "SAML_AUDIENCE": "https://saml.bettercollected.test",
    }.items():
        monkeypatch.setattr(sso, key, value)
    polis = FakePolisAdmin()
    auth = FakeAuth()
    monkeypatch.setattr(container.sso_connection_service(), "_polis", polis)
    monkeypatch.setattr(
        container.sso_connection_service(), "_resolver", public_resolver
    )
    monkeypatch.setattr(container.sso_login_service(), "_http", auth)
    monkeypatch.setattr(container.sso_policy_service(), "_http_client", auth)
    monkeypatch.setattr(container.auth_service(), "http_client", auth)
    monkeypatch.setattr(container.workspace_service(), "http_client", auth)
    return polis, auth


async def verify_domain(workspace_id, domain=DOMAIN, lost=False):
    """A verified claim, as if the TXT record had been checked."""
    return await container.workspace_domain_repo().create(
        WorkspaceDomainDocument(
            id=PydanticObjectId(),
            workspace_id=PydanticObjectId(workspace_id),
            domain=domain,
            verification_token="0" * 32,
            created_by="test",
            status=DomainStatus.VERIFIED,
            verified_domain=domain,
            verification_lost_at=dt.datetime.now(dt.timezone.utc) if lost else None,
        )
    )


async def add_connection(
    workspace_id, enabled=True, tested=True, client_id=None
) -> SsoConnectionDocument:
    now = dt.datetime.now(dt.timezone.utc)
    return await container.sso_connection_repo().create(
        SsoConnectionDocument(
            id=PydanticObjectId(),
            workspace_id=PydanticObjectId(workspace_id),
            type=SsoConnectionType.SAML,
            name="Acme IdP",
            status=(
                SsoConnectionStatus.ENABLED if enabled else SsoConnectionStatus.DISABLED
            ),
            polis_client_id=client_id or f"client-{PydanticObjectId()}",
            polis_tenant=str(workspace_id),
            polis_product="bettercollected",
            created_by="test",
            enabled_at=now if enabled else None,
            tested_at=now if tested else None,
        )
    )


def state_of(location: str) -> str:
    return parse_qs(urlsplit(location).query)["state"][0]


def query_of(location: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}
