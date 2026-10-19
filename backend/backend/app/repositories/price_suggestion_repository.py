from typing import List

from beanie import PydanticObjectId

from backend.app.schemas.price_suggestion import PriceSuggestion
from common.db.routing import write_op


class PriceSuggestionRepository:
    """Prices users suggested when upgrading (refdata group)."""

    @write_op(replay=True)
    async def add(self, suggestion: PriceSuggestion) -> PriceSuggestion:
        return await suggestion.save()

    async def list_by_user_id(self, user_id: PydanticObjectId) -> List[PriceSuggestion]:
        return await PriceSuggestion.find(
            {"user_id": PydanticObjectId(user_id)}
        ).to_list()
