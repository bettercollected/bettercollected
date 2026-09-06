"""The Postgres twins of the google repositories behave like the Mongo originals.

Mongo is the test database named by MONGO_URI/MONGO_DB (emptied here);
Postgres is the test database named by DATABASE_URL.
"""

from typing import Any

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from pymongo import AsyncMongoClient

from common.db.routing import WriteResult, normalise_result
from common.enums.form_provider import FormProvider
from googleform.app.containers import Container
from googleform.app.repositories.form import FormRepository
from googleform.app.repositories.form_response import FormResponseRepository
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.repositories.postgres import (
    PostgresFormRepository,
    PostgresFormResponseRepository,
    PostgresOauthCredentialRepository,
)
from googleform.app.schemas.google_form import GoogleFormDocument
from googleform.app.schemas.google_form_response import GoogleFormResponseDocument
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
    await database_service.init_db()
    client = AsyncMongoClient(settings.mongo_settings.URI)
    await client.drop_database(settings.mongo_settings.DB)
    yield Container.pg_sessionmaker()
    await client.drop_database(settings.mongo_settings.DB)
    await client.close()
    await database_service.close_db()
    await Container.pg_engine().dispose()


def form(form_id, title):
    return GoogleFormDocument(
        id=PydanticObjectId(), formId=form_id, info={"title": title}
    )


def response(form_id, response_id):
    return GoogleFormResponseDocument(
        id=PydanticObjectId(), formId=form_id, responseId=response_id, answers={}
    )


async def test_forms(stores):
    mongo, postgres = FormRepository(), PostgresFormRepository(stores)
    await parity(
        mongo,
        postgres,
        [
            ("list", lambda: ()),
            ("update", lambda: ("gf1", form("gf1", "One"))),
            ("update", lambda: ("gf2", form("gf2", "Two"))),
            ("update", lambda: ("gf1", form("gf1", "One, renamed"))),
            ("list", lambda: ()),
            ("get", lambda: ("gf1", FormProvider.GOOGLE)),
            ("get", lambda: ("nope", FormProvider.GOOGLE)),
            ("delete", lambda: ("gf1", FormProvider.GOOGLE)),
        ],
    )
    assert len(await postgres.list()) == 2  # update by formId replaced, not duplicated


async def test_form_responses(stores):
    mongo, postgres = FormResponseRepository(), PostgresFormResponseRepository(stores)
    added = [await repo.add(response("gf1", "r1")) for repo in (mongo, postgres)]
    assert strip(added[0]) == strip(added[1])
    for repo in (mongo, postgres):
        await repo.add(response("gf1", "r2"))
        await repo.add(response("gf2", "r3"))
    await parity(
        mongo,
        postgres,
        [
            ("list", lambda: ()),
            ("list_form_responses", lambda: ("gf1",)),
            ("list_form_responses", lambda: ("none",)),
            ("get", lambda: ("r2", FormProvider.GOOGLE)),
            ("get", lambda: ("zz", FormProvider.GOOGLE)),
            ("update", lambda: ("r2", response("gf1", "r2"))),
            ("delete", lambda: ("r3",)),
            ("delete", lambda: ("r3",)),
            ("list", lambda: ()),
        ],
    )


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
