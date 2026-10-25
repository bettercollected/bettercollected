"""The google credential repository (Postgres only): stored encrypted,
handed out decrypted, updated in place and erased by email or user id.

Postgres is the test database named by DATABASE_URL; no Mongo is used.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from googleform.app.containers import Container
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.services import database_service
from googleform.db.models import OAuthCredentialRow

pytestmark = pytest.mark.asyncio

CREDS = {"token": "t", "refresh_token": "r", "expiry": "2030-01-01T00:00:00Z"}


@pytest_asyncio.fixture
async def repo(clean_postgres):
    await database_service.init_db()
    yield OauthCredentialRepository(Container.pg_sessionmaker())
    await database_service.close_db()
    await Container.pg_engine().dispose()


async def stored_rows():
    async with Container.pg_sessionmaker()() as session:
        return (await session.execute(select(OAuthCredentialRow))).scalars().all()


async def test_credentials_are_stored_encrypted_and_read_decrypted(repo):
    saved = await repo.add("a@example.com", CREDS, user_id="u1")
    assert isinstance(saved.credentials, bytes)  # stored encrypted

    (row,) = await stored_rows()
    assert (row.email, row.user_id, row.provider) == ("a@example.com", "u1", "google")
    assert set(row.doc["credentials"]) == {"$binary"}  # ciphertext

    current = await repo.get("a@example.com")
    assert current.user_id == "u1"
    assert (current.credentials.token, current.credentials.refresh_token) == ("t", "r")
    assert await repo.get("nobody@example.com") is None


async def test_an_update_stores_ciphertext_and_returns_plaintext(repo):
    await repo.add("a@example.com", CREDS, user_id="u1")
    current = await repo.get("a@example.com")
    current.credentials.token = "t2"

    result = await repo.update("a@example.com", current)

    assert result.credentials.token == "t2"  # the caller sees plaintext
    (row,) = await stored_rows()  # updated in place, not added
    assert str(row.id) == str(current.id)
    assert (await repo.get("a@example.com")).credentials.token == "t2"
    listed = await repo.list_all()
    assert len(listed) == 1 and isinstance(listed[0].credentials, bytes)


@pytest.mark.parametrize(
    "email,user_id", [("a@example.com", "other"), ("other@example.com", "u1")]
)
async def test_an_erasure_matches_the_email_or_the_user_id(repo, email, user_id):
    await repo.add("a@example.com", CREDS, user_id="u1")
    await repo.add("b@example.com", CREDS, user_id="u2")

    assert await repo.delete_oauth_credential_for_user(email, user_id)

    assert await repo.get("a@example.com") is None
    assert (await repo.get("b@example.com")).user_id == "u2"


async def test_save_stores_a_listed_document_as_it_is(repo):
    await repo.add("a@example.com", CREDS, user_id="u1")
    (document,) = await repo.list_all()
    document.state = "s9"

    await repo.save(document)

    (row,) = await stored_rows()
    assert row.state == "s9"
    assert (await repo.get("a@example.com")).credentials.token == "t"
