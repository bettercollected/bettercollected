"""The google credential repository (Postgres only): stored encrypted,
handed out decrypted, updated in place and erased by user id (by email
only the legacy rows without one).

Postgres is the test database named by DATABASE_URL; no Mongo is used.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from googleform.app.containers import Container
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.db.models import OAuthCredentialRow

pytestmark = pytest.mark.asyncio

CREDS = {"token": "t", "refresh_token": "r", "expiry": "2030-01-01T00:00:00Z"}


@pytest_asyncio.fixture
async def repo(clean_postgres):
    yield OauthCredentialRepository(Container.pg_sessionmaker())
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
    "email,user_id", [("a@example.com", "u1"), ("other@example.com", "u1")]
)
async def test_an_erasure_matches_the_user_id(repo, email, user_id):
    await repo.add("a@example.com", CREDS, user_id="u1")
    await repo.add("b@example.com", CREDS, user_id="u2")

    assert await repo.delete_oauth_credential_for_user(email, user_id)

    assert await repo.get("a@example.com") is None
    assert (await repo.get("b@example.com")).user_id == "u2"


async def test_an_erasure_by_email_alone_leaves_another_accounts_row(repo):
    """The email matches only legacy rows without a user id: a row that
    belongs to another account (same address) is not the caller's to erase."""
    await repo.add("a@example.com", CREDS, user_id="u1")

    assert not await repo.delete_oauth_credential_for_user("a@example.com", "other")

    assert (await repo.get("a@example.com")).user_id == "u1"


async def test_deleting_an_account_keeps_its_case_variants_credential(repo):
    """Two accounts whose emails differ only in case, both connected to the
    same Google account (the credential holds Google's spelling of the
    address): deleting one account's credentials, by its user id, leaves the
    other's. A legacy row without a user id still goes by its exact email."""
    await repo.add("pat@example.com", CREDS, user_id="keeper")
    await repo.add("pat@example.com", CREDS, user_id="dropped")
    for legacy in (
        {"email": "pat@example.com"},
        {"email": "pat@example.com", "user_id": ""},
    ):
        await repo.save(Oauth2CredentialDocument(**legacy))
    await repo.save(Oauth2CredentialDocument(email="Pat@example.com"))

    await repo.delete_oauth_credential_for_user("pat@example.com", "dropped")
    left = sorted((d.user_id or "", d.email) for d in await repo.list_all())
    # the keeper's own row and a legacy row of another spelling stay
    assert left == [("", "Pat@example.com"), ("keeper", "pat@example.com")]

    # an empty user id never matches every legacy row
    await repo.delete_oauth_credential_for_user("nobody@example.com", "")
    assert len(await repo.list_all()) == 2


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


# -- revocation at Google on erasure: only the account's own, unshared grants --


def _service(repo):
    from googleform.app.services.oauth_google import OauthGoogleService

    service = OauthGoogleService.__new__(OauthGoogleService)
    service.oauth_credential_repo = repo
    return service


@pytest.fixture()
def revoked(monkeypatch):
    """The refresh tokens POSTed to Google's revocation endpoint."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    from googleform.config import settings

    monkeypatch.setattr(settings, "GOOGLE_FORMS_IMPORT", "on")
    tokens = []

    async def post(url, data, headers):
        assert url == settings.GOOGLE_REVOKE_CREDENTIALS_URL
        tokens.append(data["token"])
        return SimpleNamespace(status=200)

    with patch(
        "googleform.app.services.oauth_google.AiohttpClient.post",
        AsyncMock(side_effect=post),
    ):
        yield tokens


def _creds(refresh):
    return {**CREDS, "refresh_token": refresh}


async def test_deleting_b_never_revokes_a_grant_that_a_also_holds(repo, revoked):
    """A and B (emails differ only in case) connected the same Google
    account: revoking B's token would end A's grant at Google too, so nothing
    is revoked; B's row is still deleted, A's stays."""
    await repo.add("pat@example.com", _creds("refresh-a"), user_id="a")
    await repo.add("Pat@example.com", _creds("refresh-b"), user_id="b")

    await _service(repo).delete_oauth_credentials_for_user("Pat@example.com", "b")

    assert revoked == []
    left = [(d.user_id, d.email) for d in await repo.list_all()]
    assert left == [("a", "pat@example.com")]


async def test_the_accounts_own_unshared_grant_is_revoked(repo, revoked):
    await repo.add("pat@example.com", _creds("refresh-a"), user_id="a")
    await repo.add("bo@example.com", _creds("refresh-b"), user_id="b")

    await _service(repo).delete_oauth_credentials_for_user("bo@example.com", "b")

    assert revoked == ["refresh-b"]
    assert [d.user_id for d in await repo.list_all()] == ["a"]


async def test_a_legacy_row_is_revoked_only_when_no_other_account_shares_it(
    repo, revoked
):
    """Legacy rows (no user id) are erased by exact email; their grant is
    revoked only while no other account holds a credential for that Google
    address."""
    legacy = Oauth2CredentialDocument(
        email="kim@example.com",
        credentials=GoogleCredentialResponse(**_creds("refresh-legacy")),
    )
    await repo.save(legacy)
    await repo.add("Kim@example.com", _creds("refresh-other"), user_id="other")

    await _service(repo).delete_oauth_credentials_for_user("kim@example.com", "b")
    assert revoked == []  # "other" holds the same Google address
    assert [d.user_id for d in await repo.list_all()] == ["other"]

    await repo.save(
        Oauth2CredentialDocument(
            email="lee@example.com",
            credentials=GoogleCredentialResponse(**_creds("refresh-lee")),
        )
    )
    await _service(repo).delete_oauth_credentials_for_user("lee@example.com", "c")
    assert revoked == ["refresh-lee"]
    assert [d.user_id for d in await repo.list_all()] == ["other"]
