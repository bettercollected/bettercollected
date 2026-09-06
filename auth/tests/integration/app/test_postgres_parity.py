"""The Postgres twins of the auth repositories behave like the Mongo originals.

Mongo is the suite's in-memory mock, initialised by the app; Postgres is the
real test database. Each step runs on both; results are compared with the
volatile fields stripped.
"""

from typing import Any

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from mongomock_motor import AsyncMongoMockClient

from auth.app.container import container
from auth.app.repositories.postgres import (
    PostgresProviderRepository,
    PostgresUserRepository,
)
from auth.app.repositories.provider_repository import ProviderRepository
from auth.app.repositories.user_repository import UserRepository
from auth.app.schemas.provider import Provider
from auth.app.services.database_service import init_db
from common.db.routing import normalise_result
from common.exceptions import NotFoundError

pytestmark = pytest.mark.asyncio

VOLATILE = {"id", "_id", "created_at", "updated_at", "revision_id", "last_logged_in"}


def strip(value: Any) -> Any:
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
    await init_db(AsyncMongoMockClient())
    yield container.pg_sessionmaker()
    # pooled connections belong to this test's event loop; drop them
    await container.pg_engine().dispose()


async def test_users(stores):
    mongo, postgres = UserRepository(), PostgresUserRepository(stores)
    await parity(
        mongo,
        postgres,
        [
            ("get_user_by_email", lambda: ("nobody@example.com",)),
            ("save_otp_user", lambda: ("a@example.com", "1234", 99, False)),
            ("save_otp_user", lambda: ("a@example.com", "1234", 99, True)),  # promoted
            ("save_user", lambda: ("b@example.com", "B", "Bee")),
            (
                "save_user",
                lambda: ("b@example.com", None, None, None, None, True, "img"),
            ),
            ("get_user_by_email", lambda: ("b@example.com",)),
            ("get_users_by_emails", lambda: (["a@example.com", "b@example.com", "z"],)),
            ("get_user_by_stripe_customer_id", lambda: ("cus_none",)),
        ],
    )
    a = [await repo.get_user_by_email("a@example.com") for repo in (mongo, postgres)]
    for repo, user in zip((mongo, postgres), a):
        await repo.clear_user_otp(user)
    after = [
        await repo.get_user_by_email("a@example.com") for repo in (mongo, postgres)
    ]
    assert strip(after[0]) == strip(after[1])
    assert after[1].otp_code is None and "FORM_CREATOR" in [
        str(r) for r in after[1].roles
    ]
    for repo, user in zip((mongo, postgres), a):
        assert (await repo.get_user_by_id(user.id)).email == "a@example.com"
        assert [u.email for u in await repo.get_users_by_ids([user.id])] == [
            "a@example.com"
        ]
        assert (await repo.update_last_logged_in(user.id)).last_logged_in is not None
        await repo.delete_user(user.id)
        assert await repo.get_user_by_email("a@example.com") is None
    missing = PydanticObjectId()
    for repo in (mongo, postgres):
        with pytest.raises(NotFoundError):
            await repo.get_user_by_id(missing)


async def test_providers(stores):
    mongo, postgres = ProviderRepository(), PostgresProviderRepository(stores)
    provider = Provider(
        id=PydanticObjectId(), provider_name="google", oauth_url="http://o"
    )
    await provider.save()
    await postgres.upsert(provider)
    assert strip(await mongo.get_provider("google")) == strip(
        await postgres.get_provider("google")
    )
    for repo in (mongo, postgres):
        with pytest.raises(NotFoundError):
            await repo.get_provider("nope")
