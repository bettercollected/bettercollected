"""The refdata repositories, Postgres only since 4.1. The behaviour they had
under the dual run (where these steps ran against the Mongo original too)
stays pinned here. Skipped unless DATABASE_URL points at a *_test database."""

import pytest

from backend.app.container import container
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.types.coupon_code import CouponCode
from backend.app.repositories.postgres.refdata import (
    PostgresAllowedOriginsRepository,
    PostgresCouponRepository,
    PostgresFormPluginProviderRepository,
    PostgresPriceSuggestionRepository,
    PostgresUserFeedbackRepo,
)
from backend.app.schemas.coupon_codes import CouponCodeDocument
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.schemas.price_suggestion import PriceSuggestion
from backend.app.schemas.user_feedback import UserFeedbackDocument
from common.records import RecordId


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


async def test_allowed_origins(sessions):
    repo = PostgresAllowedOriginsRepository(sessions)
    assert await repo.list_origins() == []
    added = await repo.add("https://a.example")
    await repo.add("https://b.example")
    assert added.id is not None and added.origin == "https://a.example"
    assert await repo.list_origins() == ["https://a.example", "https://b.example"]
    found = await repo.find_by_origin("https://a.example")
    assert found.id == added.id and found.created_at is not None
    assert await repo.find_by_origin("https://nope.example") is None
    await repo.delete_by_origin("https://a.example")
    assert await repo.list_origins() == ["https://b.example"]


async def test_allowed_origins_delete_removes_one_of_duplicates(sessions):
    """allowed_origins has no unique index; a delete removes one row, as
    Mongo's find_one().delete() did."""
    repo = PostgresAllowedOriginsRepository(sessions)
    await repo.add("https://dup.example")
    await repo.add("https://dup.example")
    await repo.delete_by_origin("https://dup.example")
    assert await repo.list_origins() == ["https://dup.example"]


async def test_form_plugin_providers(sessions):
    def cfg(name, url):
        return FormPluginConfigDocument(
            enabled=True,
            provider_name=name,
            provider_url=url,
            auth_callback_url=f"{url}/cb",
        )

    repo = PostgresFormPluginProviderRepository(sessions)
    assert await repo.list() == []
    await repo.add(cfg("google", "http://g"))
    await repo.add(cfg("other", "http://o"))
    assert [p.provider_name for p in await repo.list()] == ["google", "other"]
    google = await repo.get("google")
    assert google.provider_url == "http://g"
    assert await repo.get("missing") is None
    assert (await repo.get_provider_url("google")).provider_url == "http://g"
    assert await repo.get_provider_url("missing") is None
    updated = await repo.update("google", cfg("google", "http://g2"))
    assert updated.id == google.id  # replaces the stored provider
    assert (await repo.get("google")).provider_url == "http://g2"
    assert len(await repo.list()) == 2


async def test_coupons(sessions):
    repo = PostgresCouponRepository(sessions)
    codes = [CouponCode(), CouponCode(), CouponCode()]
    assert await repo.create_coupons([CouponCodeDocument(code=c) for c in codes]) == (
        "Created"
    )
    assert [c.code for c in await repo.get_all_coupons()] == codes
    first = await repo.get_coupon_by_code(codes[0])
    assert first.code == codes[0] and first.status is CouponStatus.ACTIVE
    assert await repo.get_coupon_by_code(CouponCode()) is None

    coupon = await repo.get_coupon_by_code(codes[1])
    coupon.status = list(CouponStatus)[-1]
    saved = await repo.save(coupon)
    assert saved.updated_at >= coupon.created_at
    stored = await repo.get_coupon_by_code(codes[1])
    assert stored.id == coupon.id and stored.status is list(CouponStatus)[-1]


async def test_user_feedback(sessions):
    repo = PostgresUserFeedbackRepo(sessions)
    saved = await repo.save_user_feedback(
        UserFeedbackDocument(reason_for_deletion="testing", feedback="fine")
    )
    assert saved.id is not None
    assert [f.reason_for_deletion for f in await repo.many()] == ["testing"]


async def test_price_suggestions(sessions):
    repo = PostgresPriceSuggestionRepository(sessions)
    user_id, other = RecordId(), RecordId()

    def suggestion(price):
        return PriceSuggestion(user_id=user_id, email="u@example.com", price=price)

    assert await repo.list_by_user_id(user_id) == []
    await repo.add(suggestion(5))
    await repo.add(suggestion(9))
    assert [s.price for s in await repo.list_by_user_id(user_id)] == [5, 9]
    assert [s.price for s in await repo.list_by_user_id(str(user_id))] == [5, 9]
    assert await repo.list_by_user_id(other) == []
    [first, _] = await repo.list_by_user_id(user_id)
    assert isinstance(first.user_id, RecordId) and first.user_id == user_id
