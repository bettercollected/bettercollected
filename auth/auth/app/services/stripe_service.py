import stripe
from common.enums.plan import Plans
from fastapi import Request

from auth.app.repositories.user_repository import UserRepository
from auth.app.schemas.user import UserDocument
from auth.config import settings


class StripeService:
    def __init__(
        self,
        user_repository: UserRepository,
    ):
        self.user_repository = user_repository

    async def create_checkout_session(self, user_id, price_id):
        stripe.api_key = settings.stripe_settings.secret
        checkout_session = stripe.checkout.Session.create(
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=settings.stripe_settings.success_url,
            cancel_url=settings.stripe_settings.cancel_url,
        )
        user: UserDocument = await self.user_repository.get_user_by_id(user_id)
        user.stripe_payment_id = checkout_session.id
        await user.save()
        return checkout_session.url

    async def create_portal_session(self, user_id):
        stripe.api_key = settings.stripe_settings.secret
        user: UserDocument = await self.user_repository.get_user_by_id(user_id)
        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=settings.stripe_settings.return_url,
        )
        return portal_session.url

    async def webhooks(self, request: Request):
        body = await request.body()
        webhook_secret = settings.stripe_settings.webhook_secret
        stripe_signature = request.query_params.get("stripe_signature")
        try:
            event = stripe.Webhook.construct_event(
                payload=body, sig_header=stripe_signature, secret=webhook_secret
            )
            data = event["data"]
        except Exception as e:
            return e
        event_type = event["type"]
        if event_type == "checkout.session.completed":
            stripe_payment_id = data.object.id
            stripe_customer_id = data.object.customer
            user: UserDocument = (
                await self.user_repository.get_user_by_stripe_payment_id(
                    stripe_payment_id
                )
            )
            user.stripe_customer_id = stripe_customer_id
            user.plan = Plans.PRO
            await user.save()
            return {"user": user, "upgrade": True}
        elif (
            event_type == "customer.subscription.deleted"
            or event_type == "invoice.payment_failed"
        ):
            stripe_customer_id = data.object.customer
            user: UserDocument = (
                await self.user_repository.get_user_by_stripe_customer_id(
                    stripe_customer_id
                )
            )
            user.plan = Plans.FREE
            user = await user.save()
            return {"user": user, "downgrade": True}
        elif event_type == "invoice.payment_succeeded":
            stripe_customer_id = data.object.customer
            user: UserDocument = (
                await self.user_repository.get_user_by_stripe_customer_id(
                    stripe_customer_id
                )
            )
            user.plan = Plans.PRO
            await user.save()
            return {"user": user, "upgrade": True}
