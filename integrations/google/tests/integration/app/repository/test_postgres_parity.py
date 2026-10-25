"""The Postgres twin of the google credential repository behaves like the Mongo original.

Mongo is the test database named by MONGO_URI/MONGO_DB (emptied here);
Postgres is the test database named by DATABASE_URL.
"""

from typing import Any

import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient

from common.db.routing import WriteResult, normalise_result
from googleform.app.containers import Container
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.repositories.postgres import PostgresOauthCredentialRepository
from googleform.app.services import database_service
from googleform.config import settings

pytestmark = pytest.mark.asyncio

VOLATILE = {"id", "_id", "created_at", "updated_at", "revision_id"}


def strip(value: Any) -> Any:
    if isinstance(value, WriteResult):
        value = value.value
    value = normalise_result(value)
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


async def parity(mongo, postgres, steps):
    for name, args in steps:
        m = await getattr(mongo, name)(*args())
        p = await getattr(postgres, name)(*args())
        assert strip(m) == strip(p), f"{type(mongo).__name__}.{name} differs"


@pytest_asyncio.fixture
async def stores(clean_postgres):
    await database_service.init_db(required=True)
    client = AsyncMongoClient(settings.mongo_settings.URI)
    await client.drop_database(settings.mongo_settings.DB)
    yield Container.pg_sessionmaker()
    await client.drop_database(settings.mongo_settings.DB)
    await client.close()
    await database_service.close_db()
    await Container.pg_engine().dispose()


async def test_oauth_credentials(stores):
    mongo, postgres = OauthCredentialRepository(), PostgresOauthCredentialRepository(
        stores
    )
    creds = {"token": "t", "refresh_token": "r", "expiry": "2030-01-01T00:00:00Z"}
    for repo in (mongo, postgres):
        saved = await repo.add("a@example.com", creds, user_id="u1")
        assert isinstance(saved.credentials, bytes)  # stored encrypted
    await parity(
        mongo,
        postgres,
        [
            ("get", lambda: ("a@example.com",)),  # decrypted on read
            ("get", lambda: ("nobody@example.com",)),
        ],
    )
    for repo in (mongo, postgres):
        current = await repo.get("a@example.com")
        current.credentials.token = "t2"
        result = await repo.update("a@example.com", current)
        assert result.value.credentials.token == "t2"  # caller sees plaintext
        assert isinstance(
            result.documents[0].credentials, bytes
        )  # mirror gets ciphertext
        assert (await repo.get("a@example.com")).credentials.token == "t2"
        listed = await repo.list_all()
        assert len(listed) == 1 and isinstance(listed[0].credentials, bytes)
        assert await repo.delete_oauth_credential_for_user("a@example.com", "u1")
        assert await repo.get("a@example.com") is None


async def test_deleting_an_account_keeps_its_case_variants_credential(stores):
    """Two accounts whose emails differ only in case, both connected to the
    same Google account (the credential holds Google's spelling of the
    address): deleting one account's credentials, by its user id, leaves the
    other's, in both stores. A legacy row without a user id still goes by its
    exact email."""
    from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument

    mongo, postgres = OauthCredentialRepository(), PostgresOauthCredentialRepository(
        stores
    )
    creds = {"token": "t", "refresh_token": "r", "expiry": "2030-01-01T00:00:00Z"}
    for repo in (mongo, postgres):
        await repo.add("pat@example.com", creds, user_id="keeper")
        await repo.add("pat@example.com", creds, user_id="dropped")
        for legacy in ({"email": "pat@example.com"}, {"email": "pat@example.com", "user_id": ""}):
            await repo.save(Oauth2CredentialDocument(**legacy))
        await repo.save(Oauth2CredentialDocument(email="Pat@example.com"))

        await repo.delete_oauth_credential_for_user("pat@example.com", "dropped")
        left = sorted((d.user_id or "", d.email) for d in await repo.list_all())
        # the keeper's own row and a legacy row of another spelling stay
        assert left == [("", "Pat@example.com"), ("keeper", "pat@example.com")], repo

        # an empty user id never matches every legacy row
        await repo.delete_oauth_credential_for_user("nobody@example.com", "")
        assert len(await repo.list_all()) == 2
