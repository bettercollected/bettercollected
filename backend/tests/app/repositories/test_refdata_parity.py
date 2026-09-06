"""The Postgres twin of each refdata repository behaves like the Mongo original.

Every step runs on both implementations; results are compared after stripping
the fields that legitimately differ (ids minted independently, timestamps).
Skipped unless DATABASE_URL points at a *_test database.
"""

from typing import Any

import pytest
from pymongo.results import DeleteResult, UpdateResult

from backend.app.container import container
from backend.app.models.types.coupon_code import CouponCode
from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.coupon_repository import CouponRepository
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.repositories.postgres.refdata import (
    PostgresAllowedOriginsRepository,
    PostgresCouponRepository,
    PostgresFormPluginProviderRepository,
    PostgresUserFeedbackRepo,
)
from backend.app.repositories.user_feedback import UserFeedbackRepo
from backend.app.schemas.coupon_codes import CouponCodeDocument, CouponStatus
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.schemas.user_feedback import UserFeedbackDocument
from common.db.routing import normalise_result

VOLATILE = {"id", "_id", "created_at", "updated_at", "revision_id"}


def strip(value: Any) -> Any:
    # Mongo write results carry counts the callers ignore; the twins return the count.
    if isinstance(value, DeleteResult):
        return value.deleted_count
    if isinstance(value, UpdateResult):
        return value.matched_count
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


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


async def test_allowed_origins(sessions):
    await parity(
        AllowedOriginsRepository(),
        PostgresAllowedOriginsRepository(sessions),
        [
            ("list_origins", lambda: ()),
            ("add", lambda: ("https://a.example",)),
            ("add", lambda: ("https://b.example",)),
            ("list_origins", lambda: ()),
            ("find_by_origin", lambda: ("https://a.example",)),
            ("find_by_origin", lambda: ("https://nope.example",)),
            ("delete_by_origin", lambda: ("https://a.example",)),
            ("list_origins", lambda: ()),
        ],
    )


async def test_form_plugin_providers(sessions):
    def cfg(name, url):
        return FormPluginConfigDocument(
            enabled=True,
            provider_name=name,
            provider_url=url,
            auth_callback_url=f"{url}/cb",
        )

    await parity(
        FormPluginProviderRepository(),
        PostgresFormPluginProviderRepository(sessions),
        [
            ("list", lambda: ()),
            ("add", lambda: (cfg("google", "http://g"),)),
            ("add", lambda: (cfg("typeform", "http://t"),)),
            ("list", lambda: ()),
            ("get", lambda: ("google",)),
            ("get", lambda: ("missing",)),
            ("get_provider_url", lambda: ("google",)),
            ("update", lambda: ("google", cfg("google", "http://g2"))),
            ("get", lambda: ("google",)),
            ("list", lambda: ()),
        ],
    )


async def test_coupons(sessions):
    codes = [CouponCode(), CouponCode(), CouponCode()]

    def coupon(code):
        return CouponCodeDocument(code=code)

    async def redeem(repo, code):
        doc = await repo.get_coupon_by_code(code)
        doc.status = (
            CouponStatus.EXPIRED
            if hasattr(CouponStatus, "EXPIRED")
            else list(CouponStatus)[-1]
        )
        return await repo.save(doc)

    mongo, postgres = CouponRepository(), PostgresCouponRepository(sessions)
    await parity(
        mongo,
        postgres,
        [
            ("create_coupons", lambda: ([coupon(c) for c in codes],)),
            ("get_all_coupons", lambda: ()),
            ("get_coupon_by_code", lambda: (codes[0],)),
            ("get_coupon_by_code", lambda: (CouponCode(),)),
        ],
    )
    assert strip(await redeem(mongo, codes[1])) == strip(
        await redeem(postgres, codes[1])
    )
    assert strip(await mongo.get_coupon_by_code(codes[1])) == strip(
        await postgres.get_coupon_by_code(codes[1])
    )


async def test_user_feedback(sessions):
    def feedback():
        return UserFeedbackDocument(reason_for_deletion="testing", feedback="fine")

    await parity(
        UserFeedbackRepo(),
        PostgresUserFeedbackRepo(sessions),
        [("save_user_feedback", lambda: (feedback(),))],
    )


async def test_allowed_origins_delete_removes_one_of_duplicates_like_mongo(sessions):
    """allowed_origins has no unique index; find_one().delete() removes one document."""
    mongo, postgres = AllowedOriginsRepository(), PostgresAllowedOriginsRepository(
        sessions
    )
    for repo in (mongo, postgres):
        await repo.add("https://dup.example")
        await repo.add("https://dup.example")
    await parity(
        mongo, postgres, [("delete_by_origin", lambda: ("https://dup.example",))]
    )
    assert await mongo.list_origins() == ["https://dup.example"]
    assert await postgres.list_origins() == ["https://dup.example"]
