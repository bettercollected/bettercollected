from http import HTTPStatus

from classy_fastapi import Routable, post
from common.enums.plan import Plans
from common.models.user import User
from fastapi import Depends
from starlette.responses import Response

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.price_suggestion import PriceSuggestionRequest
from backend.app.router import router
from backend.app.services.auth_cookie_service import set_tokens_to_response
from backend.app.services.price_suggestion import PriceSuggestionService
from backend.app.services.user_service import get_logged_user
from backend.config import settings


@router(prefix="/suggest-price", tags=["Price Suggestion"])
class PriceSuggestionController(Routable):
    def __init__(
        self,
        price_suggestion_service: PriceSuggestionService = container.price_suggestion_service(),
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.price_suggestion_service = price_suggestion_service

    @post("")
    async def suggest_price_and_upgrade_user(
        self,
        suggested_price: PriceSuggestionRequest,
        response: Response,
        user: User = Depends(get_logged_user),
    ):
        if not settings.ENABLE_SUGGEST_PRICE:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Service is not enabled",
            )
        await self.price_suggestion_service.save_price_suggestion_and_upgrade_user(
            suggested_price=suggested_price, user=user
        )
        user.plan = Plans.PRO
        set_tokens_to_response(user=user, response=response)
        return "Code Redeem Successful"
