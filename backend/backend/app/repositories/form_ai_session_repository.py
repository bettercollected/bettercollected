from typing import Any, Dict, Optional

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

    @write_op
    async def update_proposal(
        self,
        session_id: PydanticObjectId,
        proposal_id: str,
        fields: Dict[str, Any],
        only_if_status: Optional[str] = None,
    ) -> bool:
        """Set ``fields`` on one proposal of a session's turns and nothing
        else, so a chat turn saved at the same time keeps its messages and
        this keeps its status. With ``only_if_status``, only while the
        proposal has that status. Whether it was updated."""
        match: Dict[str, Any] = {"m.proposal.id": proposal_id}
        if only_if_status is not None:
            match["m.proposal.status"] = only_if_status
        result = await FormAISessionDocument.get_pymongo_collection().update_one(
            {"_id": session_id, "messages.proposal.id": proposal_id},
            {
                "$set": {
                    f"messages.$[m].proposal.{key}": value
                    for key, value in fields.items()
                }
            },
            array_filters=[match],
        )
        return result.modified_count == 1
