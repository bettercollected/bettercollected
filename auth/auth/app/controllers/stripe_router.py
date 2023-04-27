from beanie import PydanticObjectId
from fastapi import Body

from auth.app.container import container
from auth.app.models.request_dtos import PriceIdRequest
from auth.app.models.response_dtos import PlanResponse
from auth.app.router import router

from classy_fastapi import Routable, get, post

from auth.app.services.stripe_service import StripeService
from auth.config import settings
import stripe

from fastapi import Request, Response


@router(prefix="/stripe")
class StripeRoutes(Routable):
    def __init__(
        self,
        stripe_service: StripeService = container.stripe_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.stripe_service = stripe_service

    @get("/plans")
    async def plans(self):
        stripe.api_key = settings.stripe_settings.secret
        prices = stripe.Price.list(product=settings.stripe_settings.product_id)
        response = []
        for price in prices.data:
            response.append(
                PlanResponse(
                    price.id,
                    price.unit_amount / 100,
                    price.currency,
                    price.recurring.interval,
                )
            )
        return {"plans": response}

    @get("/session/create/checkout")
    async def checkout(self, user_id: str, price_id: str):
        return await self.stripe_service.create_checkout_session(user_id, price_id)

    @get("/session/create/portal")
    async def customer_portal(self, user_id: PydanticObjectId):
        return await self.stripe_service.create_portal_session(user_id)

    @post("/webhooks")
    async def webhooks(self, request: Request):
        return await self.stripe_service.webhooks(request)
