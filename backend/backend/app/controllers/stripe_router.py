from classy_fastapi import Routable, get, post
from fastapi import Depends, Request, Response
from gunicorn.config import User
from starlette.responses import RedirectResponse

from backend.app.container import container
from backend.app.router import router
from backend.app.services.stripe_service import StripeService
from backend.app.services.user_service import get_logged_user


@router(prefix="/stripe", tags=["Stripe"])
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
        return await self.stripe_service.get_plans()

    @get("/session/create/checkout")
    async def checkout(
        self,
        price_id: str,
        user: User = Depends(get_logged_user),
    ):
        redirect_url = await self.stripe_service.create_checkout_session(user, price_id)
        return RedirectResponse(redirect_url)

    @get("/session/create/portal")
    async def customer_portal(self, user: User = Depends(get_logged_user)):
        redirect_url = await self.stripe_service.create_portal_session(user)
        return RedirectResponse(redirect_url)

    @post("/webhooks")
    async def webhooks(self, request: Request, response: Response):
        auth_response = await self.stripe_service.webhooks(request)
        response.content = auth_response.content
        response.status_code = auth_response.status_code
        return response
