from beanie import PydanticObjectId

from backend.app.schemas.form_ai_session import FormAISessionDocument
from common.db.routing import write_op


class FormAISessionRepository:
    async def get_or_404(self, session_id: PydanticObjectId) -> FormAISessionDocument:
        """Raises the document layer's NotFoundError when missing, like Document.get."""
        return await FormAISessionDocument.get(session_id)

    @write_op
    async def save(self, session: FormAISessionDocument) -> FormAISessionDocument:
        return await session.save()
