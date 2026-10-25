"""Account changes reach the store the next request reads: sign-in codes,
names, Stripe ids and plans of an existing account.

Two layers: the services on the user repository, and the HTTP routes.
(Until 4.1 these ran on the routing repository between Mongo and Postgres;
an existing account's code, Stripe ids and plan were once saved to Mongo
only, so a code sent to an existing user could never be validated.)
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import stripe

from auth.app.container import container
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.auth_service import AuthService
from auth.app.services.stripe_service import StripeService
from auth.app.services.user_service import UserService
from common.enums.plan import Plans
from common.models.user import UserInfo


def unique_email() -> str:
    return f"repo-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def no_mail():
    with patch("auth.app.services.auth_service.MailService") as mail_service:
        mail_service.return_value.send_message = AsyncMock()
        yield mail_service


@pytest_asyncio.fixture
async def repo(clean_postgres):
    yield UserRepository(container.pg_sessionmaker())
    # pooled connections belong to this test's event loop; drop them
    await container.pg_engine().dispose()


def webhook_event(event_type: str, **data):
    return {"type": event_type, "data": SimpleNamespace(object=SimpleNamespace(**data))}


async def run_webhook(service: StripeService, event: dict):
    request = SimpleNamespace(body=AsyncMock(return_value=b"{}"), query_params={})
    with patch.object(stripe.Webhook, "construct_event", return_value=event):
        return await service.webhooks(request)


# -- the services -----------------------------------------------------------------
@pytest.mark.asyncio
async def test_otp_sign_in_of_an_existing_user_in_the_service(repo, no_mail):
    email = unique_email()
    await repo.save_user(email)  # an existing account
    service = AuthService(None, repo, None)

    await service.send_otp_to_mail(email, None, None, creator=True)

    stored = await repo.get_user_by_email(email)
    assert stored.otp_code and stored.otp_expiry
    assert stored.otp_code_for == "FORM_CREATOR"

    signed_in = await service.validate_otp(email, stored.otp_code)
    assert signed_in is not None and signed_in.sub == email
    assert (await repo.get_user_by_email(email)).otp_code is None


@pytest.mark.asyncio
async def test_a_wrong_code_is_still_refused(repo, no_mail):
    email = unique_email()
    await repo.save_user(email)
    service = AuthService(None, repo, None)
    await service.send_otp_to_mail(email, None, None, creator=False)
    assert await service.validate_otp(email, "WRONG-1") is None


@pytest.mark.asyncio
async def test_stripe_ids_and_plan_are_stored(repo, monkeypatch):
    user = await repo.save_user(unique_email())
    service = StripeService(repo)

    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        lambda **_: SimpleNamespace(id="cs_test_1", url="https://checkout.example"),
    )
    assert (
        await service.create_checkout_session(str(user.id), "price_1")
        == "https://checkout.example"
    )
    assert (await repo.get_user_by_id(user.id)).stripe_payment_id == "cs_test_1"

    result = await run_webhook(
        service,
        webhook_event("checkout.session.completed", id="cs_test_1", customer="cus_1"),
    )
    assert result["upgrade"] is True
    stored = await repo.get_user_by_id(user.id)
    assert (stored.plan, stored.stripe_customer_id) == (Plans.PRO, "cus_1")

    await run_webhook(
        service, webhook_event("customer.subscription.deleted", customer="cus_1")
    )
    assert (await repo.get_user_by_id(user.id)).plan == Plans.FREE

    await run_webhook(
        service, webhook_event("invoice.payment_succeeded", customer="cus_1")
    )
    assert (await repo.get_user_by_id(user.id)).plan == Plans.PRO

    await run_webhook(
        service, webhook_event("invoice.payment_failed", customer="cus_1")
    )
    assert (await repo.get_user_by_id(user.id)).plan == Plans.FREE


@pytest.mark.asyncio
async def test_pro_upgrade_is_stored(repo):
    user = await repo.save_user(unique_email())
    upgraded = await UserService(repo, None).upgrade_user_to_pro(user.id)
    assert upgraded.plan == Plans.PRO
    assert (await repo.get_user_by_id(user.id)).plan == Plans.PRO


@pytest.mark.asyncio
async def test_names_from_the_callback_are_stored(repo):
    email = unique_email()
    await repo.save_user(email)
    token = container.jwt_service().encode(
        UserInfo(email=email, first_name="Ada", last_name="Lovelace")
    )
    await AuthService(None, repo, None).handle_auth_callback(token)
    stored = await repo.get_user_by_email(email)
    assert (stored.first_name, stored.last_name) == ("Ada", "Lovelace")


# -- the routes -------------------------------------------------------------------
def test_otp_sign_in_of_an_existing_user_over_http(app_runner, no_mail):
    email = unique_email()
    repo = container.user_repository()
    app_runner.portal.call(repo.save_user, email)

    sent = app_runner.get(
        "auth/otp/send", params={"receiver_email": email, "creator": True}
    )
    assert sent.status_code == 200, sent.text
    code = app_runner.portal.call(repo.get_user_by_email, email).otp_code
    assert code

    validated = app_runner.get(
        "auth/otp/validate", params={"email": email, "otp_code": code}
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["user"]["sub"] == email


def test_stripe_webhook_and_upgrade_routes(app_runner, monkeypatch):
    repo = container.user_repository()
    user = app_runner.portal.call(repo.save_user, unique_email())
    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        lambda **_: SimpleNamespace(id=f"cs_{user.id}", url="https://checkout.example"),
    )
    checkout = app_runner.get(
        "stripe/session/create/checkout",
        params={"user_id": str(user.id), "price_id": "price_1"},
    )
    assert checkout.status_code == 200, checkout.text

    event = webhook_event(
        "checkout.session.completed", id=f"cs_{user.id}", customer=f"cus_{user.id}"
    )
    with patch.object(stripe.Webhook, "construct_event", return_value=event):
        hook = app_runner.post("stripe/webhooks", content=b"{}")
    assert hook.status_code == 200, hook.text
    stored = app_runner.portal.call(repo.get_user_by_id, user.id)
    assert (stored.plan, stored.stripe_customer_id) == (Plans.PRO, f"cus_{user.id}")

    event = webhook_event("customer.subscription.deleted", customer=f"cus_{user.id}")
    with patch.object(stripe.Webhook, "construct_event", return_value=event):
        app_runner.post("stripe/webhooks", content=b"{}")
    assert app_runner.portal.call(repo.get_user_by_id, user.id).plan == Plans.FREE

    upgraded = app_runner.patch(f"users/{user.id}/upgrade")
    assert upgraded.status_code == 200, upgraded.text
    assert app_runner.portal.call(repo.get_user_by_id, user.id).plan == Plans.PRO
