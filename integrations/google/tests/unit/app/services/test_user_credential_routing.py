"""The Google Forms routes read the signed-in user's credential through the
container's repository, the Postgres one (the service stores its data in
Postgres only since 4.1; on 4.0 the same lookup follows the google group's
storage flags).

The store is an in-memory stand-in that records its reads; no database and no
Google endpoint is involved. The route is the real one
(``GET /google/forms/oauth/verify``) with the token checks after the lookup
stubbed out.
"""

import ast
import uuid
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from googleform.app.asgi import get_application
from googleform.app.containers import Container
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.services.oauth_credential import OauthCredentialService
from googleform.config import settings

VERIFY = settings.API_ROOT_PATH + "/google/forms/oauth/verify"
PACKAGE = Path(__file__).resolve().parents[4] / "googleform"
REPOSITORY_CLASSES = {"OauthCredentialRepository"}


class _Store:
    """The credential repository's read side, holding plain records."""

    def __init__(self):
        self.records = {}
        self.reads = []

    async def get(self, email, provider=None, user_id=None):
        self.reads.append(email)
        return self.records.get(email)


@pytest.fixture
def client(monkeypatch):
    async def verify_oauth_token(self, email, provider=None):
        return SimpleNamespace(email=email)

    async def verify_token_validity(self, credential):
        return "token-ok"

    monkeypatch.setattr(OauthCredentialService, "verify_oauth_token", verify_oauth_token)
    monkeypatch.setattr(OauthCredentialService, "verify_token_validity", verify_token_validity)
    # No lifespan: nothing connects to Postgres.
    return TestClient(get_application(), raise_server_exceptions=False)


def _token(email, **claims):
    return jwt.encode(
        {"sub": email, "typ": "access", **claims},
        settings.AUTH_JWT_SECRET,
        algorithm="HS256",
    )


def _signed_in(client, email, **claims):
    client.cookies.set("Authorization", _token(email, **claims))


def test_the_container_repository_is_the_postgres_one():
    assert Container.oauth_credential_repo.cls is OauthCredentialRepository


def test_the_route_reads_the_credential_from_the_container_repository(client):
    store = _Store()
    email = f"route-{uuid.uuid4().hex[:8]}@example.com"
    store.records[email] = SimpleNamespace(email=email)
    _signed_in(client, email)

    with Container.oauth_credential_repo.override(providers.Object(store)):
        response = client.get(VERIFY)

    assert response.status_code == 200, response.text
    assert store.reads == [email]


def test_a_missing_credential_is_refused(client):
    store = _Store()
    email = f"route-{uuid.uuid4().hex[:8]}@example.com"
    _signed_in(client, email)

    with Container.oauth_credential_repo.override(providers.Object(store)):
        response = client.get(VERIFY)

    assert response.status_code == 401
    assert store.reads == [email]


def test_an_access_token_is_accepted(client):
    store = _Store()
    email = f"route-{uuid.uuid4().hex[:8]}@example.com"
    store.records[email] = SimpleNamespace(email=email)
    _signed_in(client, email)

    with Container.oauth_credential_repo.override(providers.Object(store)):
        assert client.get(VERIFY).status_code == 200


@pytest.mark.parametrize(
    "claims",
    [
        {"typ": "refresh"},
        {"typ": "something-else"},
        {"typ": None},
        {"typ": ""},
        {"typ": ["access"]},
    ],
)
def test_a_token_that_is_not_an_access_token_is_refused_before_any_lookup(client, claims):
    store = _Store()
    email = f"route-{uuid.uuid4().hex[:8]}@example.com"
    store.records[email] = SimpleNamespace(email=email)
    _signed_in(client, email, **claims)

    with Container.oauth_credential_repo.override(providers.Object(store)):
        response = client.get(VERIFY)

    assert response.status_code == 401
    assert store.reads == []


def test_a_token_without_a_type_is_refused(client):
    store = _Store()
    email = f"route-{uuid.uuid4().hex[:8]}@example.com"
    store.records[email] = SimpleNamespace(email=email)
    token = jwt.encode({"sub": email}, settings.AUTH_JWT_SECRET, algorithm="HS256")
    client.cookies.set("Authorization", token)

    with Container.oauth_credential_repo.override(providers.Object(store)):
        response = client.get(VERIFY)

    assert response.status_code == 401
    assert store.reads == []


def test_a_malformed_token_is_a_401(client):
    client.cookies.set("Authorization", "not-a-jwt")
    assert client.get(VERIFY).status_code == 401


def test_repositories_are_only_built_by_the_container():
    """A repository constructed elsewhere bypasses the container (and the
    session factory it is built with)."""
    hits = []
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE).as_posix()
        if relative.startswith(("app/containers/", "app/repositories/", "migrate/")):
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in REPOSITORY_CLASSES:
                hits.append(f"{relative}:{node.lineno} {name}()")
    assert hits == [], "use the container's repository:\n  " + "\n  ".join(hits)
