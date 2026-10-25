"""The google credential repository (Postgres only): stored encrypted,
handed out decrypted, updated in place and erased by email or user id.

Postgres is the test database named by DATABASE_URL; no Mongo is used.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from googleform.app.containers import Container
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
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


# A credential is never stored in plain text. The key is derived from the user
# id; a legacy row connected by an older version has none.

LEGACY = "legacy@example.com"


async def _legacy_row(repo):
    await repo.save(
        Oauth2CredentialDocument(
            email=LEGACY,
            provider="google",
            credentials=GoogleCredentialResponse(token="old", refresh_token="old-r"),
        )
    )
    document = await repo.get(LEGACY)
    assert document.user_id is None
    return document


async def test_an_update_of_a_legacy_row_without_user_id_writes_nothing(repo):
    document = await _legacy_row(repo)
    document.credentials.token = "new"
    document.credentials.refresh_token = "new-r"

    result = await repo.update(LEGACY, document)

    assert result.credentials.token == "new"  # the caller keeps it for this request
    (row,) = await stored_rows()
    assert row.user_id is None
    assert (row.doc["credentials"]["token"], row.doc["credentials"]["refresh_token"]) == (
        "old",
        "old-r",
    )
    assert (await repo.get(LEGACY)).credentials.token == "old"


async def test_a_legacy_row_takes_the_callers_user_id_and_is_encrypted(repo):
    document = await _legacy_row(repo)
    document.credentials = GoogleCredentialResponse(token="new", refresh_token="new-r")
    document.user_id = "u-legacy"

    await repo.update(LEGACY, document)

    (row,) = await stored_rows()
    assert row.user_id == "u-legacy"
    assert set(row.doc["credentials"]) == {"$binary"}  # ciphertext
    current = await repo.get(LEGACY)
    assert (current.credentials.token, current.credentials.refresh_token) == ("new", "new-r")


async def test_an_update_without_a_stored_row_writes_nothing(repo):
    item = Oauth2CredentialDocument(
        email="nobody@example.com",
        provider="google",
        user_id="u-nobody",
        credentials=GoogleCredentialResponse(token="new", refresh_token="new-r"),
    )

    result = await repo.update("nobody@example.com", item)

    assert result.credentials.token == "new"
    assert await stored_rows() == []
