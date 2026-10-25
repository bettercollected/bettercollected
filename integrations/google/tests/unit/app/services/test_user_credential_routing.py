"""The Google Forms routes read the signed-in user's credential through the
container's routed repository, so the lookup follows the google group's flags
(DB_READ_SOURCE / DB_WRITE_MODE and their ``__google`` overrides).

The two stores are in-memory stand-ins that record their reads; no database
and no Google endpoint is involved. The route is the real one
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

from common.db import RoutingRepository, load_flags
from googleform.app.asgi import get_application
from googleform.app.containers import Container
from googleform.app.services.oauth_credential import OauthCredentialService
from googleform.config import settings

VERIFY = settings.API_ROOT_PATH + "/google/forms/oauth/verify"
PACKAGE = Path(__file__).resolve().parents[4] / "googleform"
REPOSITORY_CLASSES = {"OauthCredentialRepository", "PostgresOauthCredentialRepository"}


class _Store:
    """One store's side of the credential repository, holding plain records."""

    def __init__(self, name: str):
        self.name = name
        self.records = {}
        self.reads = []

    async def get(self, email, provider=None, user_id=None):
        self.reads.append(email)
        return self.records.get(email)


def _routed(env):
    mongo, postgres = _Store("mongo"), _Store("postgres")
    repository = RoutingRepository(
        group="google", flags=load_flags(env), mongo=mongo, postgres=postgres
    )
    return repository, {"mongo": mongo, "postgres": postgres}


@pytest.fixture
def client(monkeypatch):
    async def verify_oauth_token(self, email, provider=None):
        return SimpleNamespace(email=email)

    async def verify_token_validity(self, credential):
        return "token-ok"

    monkeypatch.setattr(OauthCredentialService, "verify_oauth_token", verify_oauth_token)
    monkeypatch.setattr(OauthCredentialService, "verify_token_validity", verify_token_validity)
    # No lifespan: nothing connects to Mongo or Postgres.
    return TestClient(get_application(), raise_server_exceptions=False)


def _signed_in(client, email):
    token = jwt.encode({"sub": email}, settings.AUTH_JWT_SECRET, algorithm="HS256")
    client.cookies.set("Authorization", token)


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"DB_READ_SOURCE": "mongo", "DB_WRITE_MODE": "mongo"}, "mongo"),
        ({"DB_READ_SOURCE": "mongo", "DB_WRITE_MODE": "dual"}, "mongo"),
        ({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "dual"}, "postgres"),
        ({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres_primary_dual"}, "postgres"),
        ({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"}, "postgres"),
        (
            {
                "DB_READ_SOURCE": "mongo",
                "DB_WRITE_MODE": "mongo",
                "DB_READ_SOURCE__google": "postgres",
                "DB_WRITE_MODE__google": "postgres_primary_dual",
            },
            "postgres",
        ),
        (
            {
                "DB_READ_SOURCE": "postgres",
                "DB_WRITE_MODE": "postgres",
                "DB_READ_SOURCE__google": "mongo",
                "DB_WRITE_MODE__google": "dual",
            },
            "mongo",
        ),
    ],
)
def test_the_route_reads_the_credential_from_the_flagged_store(client, env, expected):
    repository, stores = _routed(env)
    other = "postgres" if expected == "mongo" else "mongo"
    email = f"route-{uuid.uuid4().hex[:8]}@example.com"
    stores[expected].records[email] = SimpleNamespace(email=email)
    _signed_in(client, email)

    with Container.oauth_credential_repo.override(providers.Object(repository)):
        response = client.get(VERIFY)

    assert response.status_code == 200, response.text
    assert stores[expected].reads == [email]
    assert stores[other].reads == []


@pytest.mark.parametrize(
    "env, only_in",
    [
        ({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"}, "mongo"),
        ({"DB_READ_SOURCE": "mongo", "DB_WRITE_MODE": "mongo"}, "postgres"),
    ],
)
def test_a_credential_only_in_the_other_store_is_not_found(client, env, only_in):
    repository, stores = _routed(env)
    email = f"route-{uuid.uuid4().hex[:8]}@example.com"
    stores[only_in].records[email] = SimpleNamespace(email=email)
    _signed_in(client, email)

    with Container.oauth_credential_repo.override(providers.Object(repository)):
        response = client.get(VERIFY)

    assert response.status_code == 401
    assert stores[only_in].reads == []


def test_repositories_are_only_built_by_the_container():
    """A repository constructed elsewhere bypasses the routing and the flags."""
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
    assert hits == [], "use the container's routed repository:\n  " + "\n  ".join(hits)
