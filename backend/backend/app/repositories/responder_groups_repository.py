from typing import List

from beanie import PydanticObjectId
from pydantic import EmailStr

from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupEmailsDocument,
    ResponderGroupFormDocument,
)


class ResponderGroupsRepository:
    async def create_group(
        self, workspace_id: PydanticObjectId, name: str, emails: List[EmailStr]
    ):
        responder_group = ResponderGroupDocument(name=name, workspace_id=workspace_id)
        responder_group = await responder_group.save()
        responder_group_emails = []
        if not emails:
            return responder_group
        for email in emails:
            responder_group_emails.append(
                ResponderGroupEmailsDocument(group_id=responder_group.id, email=email)
            )
            await ResponderGroupEmailsDocument.insert_many(responder_group_emails)
        return responder_group

    async def get_group_in_workspace(
        self, workspace_id: PydanticObjectId, group_id: PydanticObjectId
    ):
        return await ResponderGroupDocument.find_one(
            {"workspace_id": workspace_id, "_id": group_id}
        )

    async def add_emails_to_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        emails = list(set(emails))
        existing_email_documents = await ResponderGroupEmailsDocument.find(
            {"group_id": group_id, "email": {"$in": emails}}
        ).to_list()
        existing_emails = [
            ex_document.email for ex_document in existing_email_documents
        ]
        new_emails = []
        for email in emails:
            if email not in existing_emails:
                new_emails.append(
                    ResponderGroupEmailsDocument(group_id=group_id, email=email)
                )
        if new_emails:
            await ResponderGroupEmailsDocument.insert_many(new_emails)

    async def remove_emails_from_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        await ResponderGroupEmailsDocument.find(
            {"group_id": group_id, "email": {"$in": emails}}
        ).delete()

    async def get_emails_in_group(self, group_id: PydanticObjectId):
        responder_groups = (
            await ResponderGroupDocument.find({"_id": group_id})
            .aggregate(
                [
                    {
                        "$lookup": {
                            "from": "responder_group_email",
                            "localField": "_id",
                            "foreignField": "group_id",
                            "as": "emails",
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "name": 1,
                            "workspace_id": 1,
                            "emails": {"email": 1},
                        }
                    },
                ]
            )
            .to_list()
        )
        return responder_groups[0] if len(responder_groups) > 0 else None

    async def remove_responder_group(self, group_id: PydanticObjectId):
        await ResponderGroupDocument.find({"_id": group_id}).delete()
        await ResponderGroupEmailsDocument.find({"group_id": group_id}).delete()

    async def get_groups_in_workspace(self, workspace_id: PydanticObjectId):
        return await ResponderGroupDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    async def add_group_to_form(self, form_id: str, group_id: PydanticObjectId):
        existing_document = await ResponderGroupFormDocument.find_one(
            {"form_id": form_id, "group_id": group_id}
        )
        if not existing_document:
            responder_group_form_document = ResponderGroupFormDocument(
                form_id=form_id, group_id=group_id
            )
            return await responder_group_form_document.save()
        return existing_document

    async def remove_group_from_form(self, form_id: str, group_id: PydanticObjectId):
        return await ResponderGroupFormDocument.find_one(
            {"form_id": form_id, "group_id": group_id}
        ).delete()
