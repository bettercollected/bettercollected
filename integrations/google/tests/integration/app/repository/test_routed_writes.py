"""Revoking a Google credential removes it through the routed repository, so
no store keeps a credential that was revoked (before, only Mongo's copy was
deleted and a Postgres-served group still found it).

Runs with the suite's flags (CI: mongo, dual, postgres) and, whatever those
are, on the read switch (Postgres read, both stores written).
"""

from types import SimpleNamespace

import pytest

from common.db import DbFlags, ReadSource, RoutingRepository, WriteMode
from googleform.app.containers import Container
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.repositories.postgres import PostgresOauthCredentialRepository
from googleform.app.services import oauth_google
from googleform.app.services.oauth_google import OauthGoogleService
from tests.integration.app.repository.test_postgres_parity import stores  # noqa: F401

pytestmark = pytest.mark.asyncio

CREDS = {
    "token": "t",
    "refresh_token": "r",
    "client_id": "c",
    "client_secret": "s",
    "token_uri": "https://oauth2.example/token",
    "expiry": "2030-01-01T00:00:00Z",
}


def routed_repositories(sessions):
    yield "suite flags", Container.oauth_credential_repo()
    for mode in (WriteMode.DUAL, WriteMode.POSTGRES_PRIMARY_DUAL):
        yield f"read switch ({mode.value})", RoutingRepository(
            group="google",
            flags=DbFlags(default_read=ReadSource.POSTGRES, default_write=mode),
            mongo=OauthCredentialRepository(),
            postgres=PostgresOauthCredentialRepository(sessions),
        )


async def test_a_revoked_credential_is_removed_from_every_store(stores, monkeypatch):
    calls = []

    def revoke_at_google(**kwargs):
        calls.append(kwargs["url"])
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(oauth_google.requests, "post", revoke_at_google)
    mongo, postgres = OauthCredentialRepository(), PostgresOauthCredentialRepository(
        stores
    )
    for label, routed in routed_repositories(stores):
        email = f"revoke-{len(calls)}@example.com"
        await routed.add(email, CREDS, user_id=f"u{len(calls)}")
        credential = await routed.get(email)
        assert credential is not None, label

        assert await OauthGoogleService(routed).revoke(credential) is True, label

        assert await routed.get(email) is None, label
        assert await postgres.get(email) is None, label
        assert await mongo.get(email) is None, label
    assert len(calls) == 3


async def test_a_credential_google_did_not_revoke_is_kept(stores, monkeypatch):
    monkeypatch.setattr(
        oauth_google.requests, "post", lambda **_: SimpleNamespace(status_code=400)
    )
    routed = Container.oauth_credential_repo()
    await routed.add("kept@example.com", CREDS, user_id="u-kept")
    credential = await routed.get("kept@example.com")
    assert await OauthGoogleService(routed).revoke(credential) is False
    assert await routed.get("kept@example.com") is not None
