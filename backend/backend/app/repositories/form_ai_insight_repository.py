from typing import Optional

from beanie import PydanticObjectId

from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from common.db.routing import write_op


class FormAIInsightRepository:
    async def find(
        self, workspace_id: PydanticObjectId, form_id: str
    ) -> Optional[FormAIInsightDocument]:
        return await FormAIInsightDocument.find_one(
            {"workspace_id": workspace_id, "form_id": form_id}
        )

    @write_op
    async def save(self, document: FormAIInsightDocument) -> FormAIInsightDocument:
        return await document.save()
