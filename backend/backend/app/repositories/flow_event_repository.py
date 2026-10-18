from datetime import datetime
from typing import List

from backend.app.schemas.flow_event import FlowEventDocument
from common.db.routing import write_op


class FlowEventRepository:
    @write_op(replay=True)
    async def add(
        self, form_id: str, session_id: str, from_page: str, to_page: str
    ) -> FlowEventDocument:
        return await FlowEventDocument(
            form_id=form_id, session_id=session_id, from_page=from_page, to_page=to_page
        ).save()

    async def list_by_form_id(self, form_id: str) -> List[FlowEventDocument]:
        return await FlowEventDocument.find({"form_id": form_id}).to_list()

    @write_op
    async def delete_older_than(self, cutoff: datetime) -> int:
        """Events recorded before ``cutoff`` (MongoDB's TTL index normally
        does this; kept for parity with the Postgres repository)."""
        result = await FlowEventDocument.find(
            {"created_at": {"$lt": cutoff}}
        ).delete()
        return result.deleted_count if result else 0
