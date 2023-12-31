from classy_fastapi import Routable, get, post
from fastapi import Depends, Request, Response
from gunicorn.config import User
from starlette.responses import RedirectResponse

from backend.app.container import container
from backend.app.router import router
from backend.app.services.stripe_service import StripeService
from backend.app.services.user_service import get_logged_user


@router(
    prefix="/stripe",
    tags=["Stripe"],
    responses={
        401: {"description": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class StripeRoutes(Routable):
    def __init__(
        self,
        stripe_service: StripeService = container.stripe_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.stripe_service = stripe_service

    @get("/plans", responses={503: {"message": "Requested Source not available."}})
    async def plans(self):
        return await self.stripe_service.get_plans()

    @get(
        "/session/create/checkout",
    )
    async def checkout(
        self,
        price_id: str,
        user: User = Depends(get_logged_user),
    ):
        redirect_url = await self.stripe_service.create_checkout_session(user, price_id)
        return RedirectResponse(redirect_url)

    @get(
        "/session/create/portal",
        responses={
            503: {"message": "Requested Source not available."},
        },
    )
    async def customer_portal(self, user: User = Depends(get_logged_user)):
        redirect_url = await self.stripe_service.create_portal_session(user)
        return RedirectResponse(redirect_url)

    @post(
        "/webhooks",
        responses={
            503: {"message": "Requested Source not available."},
            400: {"message": "Unable to extract timestamp and signatures from header"},
        },
    )
    async def webhooks(self, request: Request):
        return await self.stripe_service.webhooks(request)
