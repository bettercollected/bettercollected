from typing import List

from beanie import PydanticObjectId
from pydantic import EmailStr

from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupEmailsDocument,
)


class ResponderGroupsRepository:
    async def create_group(
        self, workspace_id: PydanticObjectId, name: str, emails: List[EmailStr]
    ):
        responder_group = ResponderGroupDocument(name=name, workspace_id=workspace_id)
        responder_group = await responder_group.save()
        responder_group_emails = []
        for email in emails:
            responder_group_emails.append(
                ResponderGroupEmailsDocument(group_id=responder_group.id, email=email)
            )
            await ResponderGroupEmailsDocument.insert_many(responder_group_emails)
        return responder_group
