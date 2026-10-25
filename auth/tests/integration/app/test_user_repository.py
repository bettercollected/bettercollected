"""The account repository on Postgres (the only store since 4.1).

These were parity tests against the Mongo repository until 4.1; the
expectations are what both stores returned then.
"""

import datetime as dt
import os

import pytest
import pytest_asyncio

from auth.app.container import container
from auth.app.repositories.user_repository import UserRepository
from auth.app.schemas.user import UserDocument
from common.enums.plan import Plans
from common.exceptions import NotFoundError
from common.ids import RecordId

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def repo(clean_postgres):
    yield UserRepository(container.pg_sessionmaker())
    # pooled connections belong to this test's event loop; drop them
    await container.pg_engine().dispose()


async def test_users(repo):
    assert await repo.get_user_by_email("nobody@example.com") is None

    responder = await repo.save_otp_user("a@example.com", "1234", 99, False)
    assert (responder.otp_code, responder.otp_expiry) == ("1234", 99)
    assert responder.otp_code_for == "FORM_RESPONDER"
    assert responder.roles == []
    promoted = await repo.save_otp_user("a@example.com", "1234", 99, True)
    assert promoted.id == responder.id and promoted.otp_code_for == "FORM_CREATOR"

    created = await repo.save_user("b@example.com", "B", "Bee")
    assert (created.first_name, created.last_name) == ("B", "Bee")
    assert created.roles == ["FORM_RESPONDER", "FORM_CREATOR"]
    assert created.plan == Plans.FREE
    # names are kept once all three are set; a missing image is filled in
    again = await repo.save_user("b@example.com", None, None, None, None, True, "img")
    assert again.id == created.id
    assert (again.first_name, again.last_name, again.profile_image) == (
        "B",
        "Bee",
        "img",
    )
    stored = await repo.get_user_by_email("b@example.com")
    assert (stored.first_name, stored.profile_image) == ("B", "img")

    found = await repo.get_users_by_emails(["a@example.com", "b@example.com", "z"])
    assert [u.email for u in found] == ["a@example.com", "b@example.com"]
    assert await repo.get_user_by_stripe_customer_id("cus_none") is None

    # every lookup ignores case (literal: no pattern characters); the stored
    # address keeps the case it was written with
    mixed = await repo.save_user("Mixed.Case+1@Example.com", "M")
    for email in ("mixed.case+1@example.com", "MIXED.CASE+1@EXAMPLE.COM"):
        assert (await repo.get_user_by_email(email)).id == mixed.id
    assert await repo.get_user_by_email("mixedXcase+1@example.com") is None
    assert await repo.get_user_by_email("") is None
    found = await repo.get_users_by_emails(
        ["MIXED.case+1@example.com", "B@EXAMPLE.COM"]
    )
    assert sorted(u.email for u in found) == [
        "Mixed.Case+1@Example.com",
        "b@example.com",
    ]
    # a case variant signs in to the same account, never a second one
    again = await repo.save_user("mixed.case+1@EXAMPLE.com", "Other")
    assert again.id == mixed.id and again.email == "Mixed.Case+1@Example.com"
    assert await repo.count() == 3

    user = await repo.get_user_by_email("a@example.com")
    await repo.clear_user_otp(user)
    after = await repo.get_user_by_email("a@example.com")
    assert (after.otp_code, after.otp_expiry, after.otp_code_for) == (None, None, None)
    assert after.roles == ["FORM_RESPONDER", "FORM_CREATOR"]
    assert after.updated_at == user.updated_at  # an update, not a save

    assert (await repo.get_user_by_id(user.id)).email == "a@example.com"
    assert [u.email for u in await repo.get_users_by_ids([user.id])] == [
        "a@example.com"
    ]
    assert (await repo.update_last_logged_in(user.id)).last_logged_in is not None
    await repo.delete_user(user.id)
    assert await repo.get_user_by_email("a@example.com") is None
    with pytest.raises(NotFoundError):
        await repo.get_user_by_id(RecordId())


async def test_emails_are_unique_ignoring_case(repo):
    """``uq_users_email_lower`` refuses a second account for an address that
    differs only in case, whichever path writes it."""
    await repo.save_user("Jane@Example.com")
    with pytest.raises(Exception, match="uq_users_email_lower"):
        await repo.save_document(UserDocument(email="jane@example.COM"))
    assert await repo.count() == 1


async def test_user_metrics(repo):
    """The platform-metrics counts: users dated by id, activity by
    last_logged_in, a missing plan counted as FREE."""
    now = dt.datetime(2026, 3, 18, 12, tzinfo=dt.timezone.utc)
    weeks = [dt.datetime(2026, 3, d, tzinfo=dt.timezone.utc) for d in (2, 9, 16, 23)]

    def user(email, created, last_logged_in=None, plan=Plans.FREE):
        stamp = RecordId.from_datetime(created).binary[:4]
        return UserDocument(
            id=RecordId(stamp + os.urandom(8)),
            email=email,
            last_logged_in=last_logged_in,
            plan=plan,
        )

    users = [
        user(
            "old@example.com", now - dt.timedelta(days=90), now - dt.timedelta(days=2)
        ),
        user("pro@example.com", weeks[1], now - dt.timedelta(days=40), Plans.PRO),
        user("new@example.com", now - dt.timedelta(hours=3), now.replace(tzinfo=None)),
        user("noplan@example.com", now - dt.timedelta(days=12), plan=None),
    ]
    for document in users:
        await repo.upsert(document)

    since = now - dt.timedelta(days=30)
    assert await repo.count_users() == 4
    assert await repo.count_users(since) == 3
    assert await repo.count_users_active_since(since) == 2
    assert await repo.count_users_by_plan() == {"FREE": 3, "PRO": 1}
    assert await repo.count_users_created_per_period(weeks) == [1, 1, 1]
    assert await repo.count_users_created_per_period(weeks[:1]) == []
    # every plan is listed, also one nobody is on
    await repo.delete_user(users[1].id)
    assert await repo.count_users_by_plan() == {"FREE": 3, "PRO": 0}


async def test_user_field_updates(repo):
    """The targeted updates of an existing account (sign-in code, names,
    Stripe ids, plan) store the whole account."""
    user = await repo.save_user("upd@example.com")

    after = await repo.set_user_otp(user.id, "ABC-123", 99, "FORM_CREATOR")
    assert after.otp_code == "ABC-123" and after.otp_code_for == "FORM_CREATOR"
    after = await repo.update_user_names(user.id, "Ada", None)
    assert (after.first_name, after.last_name) == ("Ada", None)
    after = await repo.set_stripe_payment_id(user.id, "cs_1")
    assert after.stripe_payment_id == "cs_1"
    assert (await repo.get_user_by_stripe_payment_id("cs_1")).id == user.id
    after = await repo.set_user_plan(user.id, Plans.PRO, stripe_customer_id="cus_1")
    assert (after.plan, after.stripe_customer_id) == (Plans.PRO, "cus_1")
    after = await repo.set_user_plan(user.id, Plans.FREE)
    assert (after.plan, after.stripe_customer_id) == (Plans.FREE, "cus_1")
    assert after.updated_at > user.updated_at  # a save moves updated_at

    stored = await repo.get_user_by_email("upd@example.com")
    assert stored.model_dump() == after.model_dump()
    assert (await repo.get_user_by_stripe_customer_id("cus_1")).id == user.id
    with pytest.raises(NotFoundError):
        await repo.set_user_plan(RecordId(), Plans.PRO)
