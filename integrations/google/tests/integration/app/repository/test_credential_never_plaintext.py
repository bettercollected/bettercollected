"""A credential update never stores Google tokens in plain text.

The tokens are encrypted with a key derived from the user id. A legacy row
connected by an older version has none: an update of it writes nothing,
unless the caller supplies the user id (the OAuth callback knows the
signed-in user). An update without a stored row writes nothing either.

Runs against the container's routed repository in whatever storage mode the
flags select, and inspects every store the mode writes.
"""

import pytest
import pytest_asyncio

from googleform.app.containers import Container
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.repositories.postgres import PostgresOauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.app.services import database_service
from tests.conftest import _truncate_postgres

pytestmark = pytest.mark.asyncio

EMAIL = "legacy@example.com"
OLD_TOKEN = "old-access-token"
NEW_TOKEN = "new-access-token"
NEW_REFRESH = "new-refresh-token"


def _plain(token=OLD_TOKEN, refresh="old-refresh-token"):
    return GoogleCredentialResponse(token=token, refresh_token=refresh)


@pytest_asyncio.fixture
async def repo():
    flags = Container.flags()
    if flags.writes_postgres("google"):
        # the schema is migrated at session start (tests/conftest.py)
        await _truncate_postgres()
    await database_service.init_db()
    if flags.writes_mongo("google"):
        await Oauth2CredentialDocument.find_all().delete()
    yield Container.oauth_credential_repo()
    if flags.writes_mongo("google"):
        await Oauth2CredentialDocument.find_all().delete()
    await database_service.close_db()
    await Container.pg_engine().dispose()


async def _stored():
    """Every credential as each written store holds it (not decrypted)."""
    flags = Container.flags()
    stores = []
    if flags.writes_mongo("google"):
        stores.append(OauthCredentialRepository())
    if flags.writes_postgres("google"):
        stores.append(PostgresOauthCredentialRepository(Container.pg_sessionmaker()))
    return [await store.list_all() for store in stores]


async def _legacy_row(repo):
    await repo.save(
        Oauth2CredentialDocument(email=EMAIL, provider="google", credentials=_plain())
    )
    document = await repo.get(EMAIL)
    assert document.user_id is None
    return document


async def test_a_legacy_row_without_user_id_is_not_written(repo):
    document = await _legacy_row(repo)
    document.credentials.token = NEW_TOKEN
    document.credentials.refresh_token = NEW_REFRESH

    result = await repo.update(EMAIL, document)

    # the caller keeps the refreshed token for this request
    assert result.credentials.token == NEW_TOKEN
    for rows in await _stored():
        assert len(rows) == 1
        stored = repr(rows[0].model_dump())
        assert NEW_TOKEN not in stored and NEW_REFRESH not in stored
    assert (await repo.get(EMAIL)).credentials.token == OLD_TOKEN


async def test_a_legacy_row_takes_the_callers_user_id_and_is_encrypted(repo):
    document = await _legacy_row(repo)
    document.credentials = _plain(NEW_TOKEN, NEW_REFRESH)
    document.user_id = "u-legacy"

    result = await repo.update(EMAIL, document)

    assert result.credentials.token == NEW_TOKEN
    for rows in await _stored():
        assert len(rows) == 1
        assert rows[0].user_id == "u-legacy"
        assert isinstance(rows[0].credentials, bytes)
        assert NEW_TOKEN not in repr(rows[0].model_dump())
    current = await repo.get(EMAIL)
    assert current.credentials.token == NEW_TOKEN
    assert current.credentials.refresh_token == NEW_REFRESH


async def test_an_update_without_a_stored_row_writes_nothing(repo):
    item = Oauth2CredentialDocument(
        email="nobody@example.com",
        provider="google",
        user_id="u-nobody",
        credentials=_plain(NEW_TOKEN, NEW_REFRESH),
    )

    result = await repo.update("nobody@example.com", item)

    assert result.credentials.token == NEW_TOKEN
    assert await repo.get("nobody@example.com") is None
    for rows in await _stored():
        assert rows == []


async def test_a_row_with_user_id_is_stored_encrypted(repo):
    await repo.add(EMAIL, dict(_plain()), user_id="u1")
    document = await repo.get(EMAIL)
    document.credentials.token = NEW_TOKEN

    await repo.update(EMAIL, document)

    for rows in await _stored():
        assert len(rows) == 1 and isinstance(rows[0].credentials, bytes)
        assert rows[0].user_id == "u1"
    assert (await repo.get(EMAIL)).credentials.token == NEW_TOKEN
