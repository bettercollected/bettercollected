from typing import Optional

from beanie import PydanticObjectId

from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument


class AIPreferenceMemoryRepository:
    async def find(
        self, workspace_id: PydanticObjectId, user_id: str
    ) -> Optional[UserAIPreferenceMemoryDocument]:
        return await UserAIPreferenceMemoryDocument.find_one(
            {"workspace_id": workspace_id, "user_id": user_id}
        )

    async def save(
        self, document: UserAIPreferenceMemoryDocument
    ) -> UserAIPreferenceMemoryDocument:
        return await document.save()
