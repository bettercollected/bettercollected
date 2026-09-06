import re
from typing import Dict, Set, List, Optional

from beanie import PydanticObjectId
from pydantic import EmailStr

from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupMemberDocument,
    ResponderGroupFormDocument,
)
from common.db import derived_object_id, to_bson_dict
from common.db.routing import write_op


class ResponderGroupsRepository:
    @staticmethod
    def member(
        group_id: PydanticObjectId, identifier: str
    ) -> ResponderGroupMemberDocument:
        """A member's identity is the (group, identifier) pair; its id follows."""
        return ResponderGroupMemberDocument(
            id=derived_object_id("responder_group_member", group_id, identifier),
            group_id=group_id,
            identifier=identifier,
        )

    @staticmethod
    def link(group_id: PydanticObjectId, form_id: str) -> ResponderGroupFormDocument:
        return ResponderGroupFormDocument(
            id=derived_object_id("responder_group_form", group_id, form_id),
            group_id=group_id,
            form_id=form_id,
        )

    @write_op(replay=True)
    async def create_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        description: Optional[str] = None,
        regex: Optional[str] = None,
    ):
        """The group document only; members and forms are added by their own
        calls (ResponderGroupsService.create_group orchestrates)."""
        if description and len(description) > 280:
            return {"message": "description should be less than 280 characters"}
        return await ResponderGroupDocument(
            name=name, workspace_id=workspace_id, description=description, regex=regex
        ).save()

    @write_op
    async def update_group(
        self,
        workspace_id: PydanticObjectId,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emails: List[EmailStr] = None,
        group_id: PydanticObjectId = None,
        regex: Optional[str] = None,
    ):
        responder_group = await ResponderGroupDocument.find_one(
            {"workspace_id": workspace_id, "_id": group_id}
        )
        if emails and len(emails) != 0:
            # replace the membership wholesale
            await ResponderGroupMemberDocument.find({"group_id": group_id}).delete()
            await ResponderGroupMemberDocument.insert_many(
                [self.member(group_id, email) for email in set(emails)]
            )

        if responder_group:
            if name:
                responder_group.name = name
            if description:
                responder_group.description = description
            responder_group.regex = regex
        return await responder_group.save()

    async def get_group_in_workspace(
        self, workspace_id: PydanticObjectId, group_id: PydanticObjectId
    ):
        return await ResponderGroupDocument.find_one(
            {"workspace_id": workspace_id, "_id": group_id}
        )

    @write_op
    async def add_emails_to_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        emails = list(set(emails))
        existing_email_documents = await ResponderGroupMemberDocument.find(
            {"group_id": group_id, "identifier": {"$in": emails}}
        ).to_list()
        existing_emails = [
            ex_document.identifier for ex_document in existing_email_documents
        ]
        new_emails = []
        for email in emails:
            if email not in existing_emails:
                new_emails.append(self.member(group_id, email))
        if new_emails:
            await ResponderGroupMemberDocument.insert_many(new_emails)

    @write_op
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
                            "regex": 1,
                            "forms": "$forms.form_id",
                        }
                    },
                ]
            )
            .to_list()
        )
        return responder_groups[0] if len(responder_groups) > 0 else None

    @write_op
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
                            "regex": 1,
                            "forms": "$forms.form_id",
                        }
                    },
                ],
                projection_model=ResponderGroupDto,
            )
            .to_list()
        )

    async def get_groups_by_form_ids(
        self, form_ids: List[str]
    ) -> Dict[str, List[dict]]:
        """form_id -> the raw responder-group documents attached to it (the
        shape a $lookup into responder_group yields), for the forms twins."""
        links = await ResponderGroupFormDocument.find(
            {"form_id": {"$in": form_ids}}
        ).to_list()
        groups = {
            group.id: to_bson_dict(group)
            for group in await ResponderGroupDocument.find(
                {"_id": {"$in": list({link.group_id for link in links})}}
            ).to_list()
        }
        by_form: Dict[str, List[dict]] = {form_id: [] for form_id in form_ids}
        for link in links:
            if link.group_id in groups:
                by_form.setdefault(link.form_id, []).append(groups[link.group_id])
        return by_form

    async def get_form_ids_accessible_to(
        self, form_ids: List[str], identifier: str
    ) -> Set[str]:
        """The subset of ``form_ids`` whose responder groups admit ``identifier``:
        a member with that identifier, or a group regex it matches."""
        links = await ResponderGroupFormDocument.find(
            {"form_id": {"$in": form_ids}}
        ).to_list()
        group_ids = list({link.group_id for link in links})
        if not group_ids:
            return set()
        member_of = {
            member.group_id
            for member in await ResponderGroupMemberDocument.find(
                {"group_id": {"$in": group_ids}, "identifier": identifier}
            ).to_list()
        }
        regex_groups = await ResponderGroupDocument.find(
            {"_id": {"$in": group_ids}, "regex": {"$nin": [None, ""]}}
        ).to_list()
        for group in regex_groups:
            try:
                if re.search(group.regex, identifier):
                    member_of.add(group.id)
            except re.error:
                continue
        return {link.form_id for link in links if link.group_id in member_of}

    @write_op
    async def add_group_to_form(self, form_id: str, group_id: PydanticObjectId):
        existing_document = await ResponderGroupFormDocument.find_one(
            {"form_id": form_id, "group_id": group_id}
        )
        if not existing_document:
            return await self.link(group_id, form_id).save()

    @write_op
    async def add_groups_to_form(self, form_id: str, group_ids: List[PydanticObjectId]):
        ids_to_add = group_ids
        existing_groups = await ResponderGroupFormDocument.find(
            {"form_id": form_id}
        ).to_list()
        ids_to_remove = [group.group_id for group in existing_groups]

        for group_id in ids_to_remove:
            if group_id in ids_to_add:
                ids_to_remove.remove(group_id)
                ids_to_add.remove(group_id)
        for group_id in ids_to_remove:
            await self.remove_group_from_form(form_id, group_id)
        for group_id in ids_to_add:
            await self.add_group_to_form(form_id, group_id)

        return await ResponderGroupFormDocument.find({"form_id": form_id}).to_list()
        # return await ResponderGroupFormDocument.find({"form_id": form_id}).aggregate([
        #     {
        #         "$lookup": {
        #             "from": "responder_group_member",
        #             "localField": "group_id",
        #             "foreignField": "group_id",
        #             "as": "emails",
        #         },
        #     },
        #     {
        #         "$lookup": {
        #             "from": "responder_group",
        #             "localField": "group_id",
        #             "foreignField": "_id",
        #             "as": "groups",
        #         }
        #     },
        #     {
        #         "$unwind": {
        #             "path": "$groups"
        #         }
        #     },
        #     {
        #         "$unset": "_id"
        #
        #     },
        #     {
        #         "$project": {
        #             "name": "$groups.name",
        #             "description": "$groups.description",
        #             "regex": "$groups.regex",
        #             "emails": "$emails.identifier",
        #             "form_id": 1
        #
        #         }
        #     },
        # ]
        # ).to_list()

    @write_op
    async def remove_group_from_form(self, form_id: str, group_id: PydanticObjectId):
        await ResponderGroupFormDocument.find_one(
            {"form_id": form_id, "group_id": group_id}
        ).delete()

    @write_op
    async def delete_workspace_form_groups(self, form_id: str):
        await ResponderGroupFormDocument.find({"form_id": form_id}).delete()

    @write_op
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
