from typing import List, Optional

from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from common.db.routing import write_op


class AllowedOriginsRepository:
    """The origins the dynamic CORS middleware accepts (seeded + custom domains)."""

    async def list_origins(self) -> List[str]:
        docs = await AllowedOriginsDocument.find().to_list()
        return [doc.origin for doc in docs]

    async def find_by_origin(self, origin: str) -> Optional[AllowedOriginsDocument]:
        return await AllowedOriginsDocument.find_one({"origin": origin})

    @write_op(replay=True)
    async def add(self, origin: str) -> AllowedOriginsDocument:
        return await AllowedOriginsDocument(origin=origin).save()

    @write_op
    async def delete_by_origin(self, origin: str) -> None:
        await AllowedOriginsDocument.find_one({"origin": origin}).delete()
