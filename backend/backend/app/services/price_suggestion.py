from http import HTTPStatus

from beanie import PydanticObjectId
from common.enums.plan import Plans
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.kafka_event_dto import UserEventType
from backend.app.models.dtos.price_suggestion import PriceSuggestionRequest
from backend.app.schemas.price_suggestion import PriceSuggestion
from backend.app.services.auth_service import AuthService
from backend.app.services.kafka_service import event_logger_service
from backend.app.services.workspace_service import WorkspaceService


class PriceSuggestionService:
    def __init__(self, auth_service: AuthService, workspace_service: WorkspaceService):
        self.auth_service: AuthService = auth_service
        self.workspace_service: WorkspaceService = workspace_service

    async def save_price_suggestion_and_upgrade_user(
        self, suggested_price: PriceSuggestionRequest, user: User
    ):
        if user.plan == Plans.PRO:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, content="Already a PRO user"
            )

        suggested_price_document = PriceSuggestion(
            user_id=PydanticObjectId(user.id),
            price=suggested_price.price,
            email=user.sub,
        )

        await suggested_price_document.save()
        await self.auth_service.upgrade_user_to_pro(user=user)
        await self.workspace_service.upgrade_user_workspace(user_id=user.id)

        await event_logger_service.send_event(
            UserEventType.USER_UPGRADED_TO_PRO, user_id=user.id, email=user.sub
        )
