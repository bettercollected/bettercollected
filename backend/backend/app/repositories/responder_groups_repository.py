from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import EmailStr

from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupMemberDocument,
    ResponderGroupFormDocument,
)


class ResponderGroupsRepository:
    async def create_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        description: Optional[str],
        form_id: Optional[str],
        emails: List[EmailStr],
    ):
        if description and len(description) > 280:
            return {"message": "description should be less than 280 characters"}
        responder_group = ResponderGroupDocument(
            name=name, workspace_id=workspace_id, description=description
        )
        responder_group = await responder_group.save()
        responder_group_emails = []
        if emails:
            for email in emails:
                responder_group_emails.append(
                    ResponderGroupMemberDocument(
                        group_id=responder_group.id, identifier=email
                    )
                )
            await ResponderGroupMemberDocument.insert_many(responder_group_emails)
        if form_id:
            await ResponderGroupFormDocument.insert(
                ResponderGroupFormDocument(group_id=responder_group.id, form_id=form_id)
            )
        return responder_group

    async def update_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        description: Optional[str],
        emails: List[EmailStr],
        group_id: PydanticObjectId,
    ):
        responder_group = await ResponderGroupDocument.find_one(
            {"workspace_id": workspace_id, "_id": group_id}
        )
        existing_group_members = await ResponderGroupMemberDocument.find(
            {"group_id": group_id}
        ).to_list()
        for existing_group_member in existing_group_members:
            for email in existing_group_member:
                await ResponderGroupMemberDocument.find(
                    {"group_id": group_id, "identifier": {"$in": email}}
                ).delete()
        responder_group_emails = []
        for email in emails:
            responder_group_emails.append(
                ResponderGroupMemberDocument(
                    group_id=responder_group.id, identifier=email
                )
            )
        await ResponderGroupMemberDocument.insert_many(responder_group_emails)

        if responder_group:
            responder_group.name = name
            responder_group.description = description
        return await responder_group.save()

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
        existing_email_documents = await ResponderGroupMemberDocument.find(
            {"group_id": group_id, "identifier": {"$in": emails}}
        ).to_list()
        existing_emails = [
            ex_document.email for ex_document in existing_email_documents
        ]
        new_emails = []
        for email in emails:
            if email not in existing_emails:
                new_emails.append(
                    ResponderGroupMemberDocument(group_id=group_id, identifier=email)
                )
        if new_emails:
            await ResponderGroupMemberDocument.insert_many(new_emails)

    async def remove_emails_from_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        await ResponderGroupMemberDocument.find(
            {"group_id": group_id, "identifier": {"$in": emails}}
        ).delete()

    async def get_emails_in_group(self, group_id: PydanticObjectId):
        responder_groups = (
            await ResponderGroupDocument.find({"_id": group_id})
            .aggregate(
                [
                    {
                        "$lookup": {
                            "from": "responder_group_member",
                            "localField": "_id",
                            "foreignField": "group_id",
                            "as": "emails",
                        }
                    },
                    {
                        "$lookup": {
                            "from": "responder_group_form",
                            "localField": "_id",
                            "foreignField": "group_id",
                            "as": "forms",
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "name": 1,
                            "workspace_id": 1,
                            "emails": "$emails.identifier",
                            "description": 1,
                            "forms": "$forms.form_id",
                        }
                    },
                ]
            )
            .to_list()
        )
        return responder_groups[0] if len(responder_groups) > 0 else None

    async def remove_responder_group(self, group_id: PydanticObjectId):
        await ResponderGroupDocument.find({"_id": group_id}).delete()
        await ResponderGroupMemberDocument.find({"group_id": group_id}).delete()
        await ResponderGroupFormDocument.find({"group_id": group_id}).delete()

    async def get_groups_in_workspace(self, workspace_id: PydanticObjectId):
        return (
            await ResponderGroupDocument.find({"workspace_id": workspace_id})
            .aggregate(
                [
                    {
                        "$lookup": {
                            "from": "responder_group_member",
                            "localField": "_id",
                            "foreignField": "group_id",
                            "as": "emails",
                        }
                    },
                    {
                        "$lookup": {
                            "from": "responder_group_form",
                            "localField": "_id",
                            "foreignField": "group_id",
                            "as": "forms",
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "name": 1,
                            "workspace_id": 1,
                            "emails": "$emails.identifier",
                            "description": 1,
                            "forms": "$forms.form_id",
                        }
                    },
                ],
                projection_model=ResponderGroupDto,
            )
            .to_list()
        )

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
        await ResponderGroupFormDocument.find_one(
            {"form_id": form_id, "group_id": group_id}
        ).delete()

    async def delete_workspace_form_groups(self, form_id: str):
        await ResponderGroupFormDocument.find({"form_id": form_id}).delete()

    async def delete_responder_groups(self, workspace_ids: List[PydanticObjectId]):
        group_ids_query = ResponderGroupDocument.find(
            {"workspace_id": {"$in": workspace_ids}}
        )
        group_ids = [group.id for group in await group_ids_query.to_list()]
        await ResponderGroupFormDocument.find({"group_id": {"$in": group_ids}}).delete()
        await ResponderGroupMemberDocument.find(
            {"group_id": {"$in": group_ids}}
        ).delete()
        await group_ids_query.delete()
