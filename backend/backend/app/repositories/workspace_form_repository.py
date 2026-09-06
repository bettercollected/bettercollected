from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from common.constants import MESSAGE_DATABASE_EXCEPTION
from common.models.user import User
from pymongo.errors import (
    InvalidOperation,
    InvalidURI,
    NetworkTimeout,
    OperationFailure,
)

from backend.app.exceptions import HTTPException
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.db.routing import write_op


class WorkspaceFormRepository:
    async def find_workspace_form(
        self, workspace_id: PydanticObjectId, form_id: str
    ) -> Optional[WorkspaceFormDocument]:
        return await WorkspaceFormDocument.find_one(
            {"form_id": form_id, "workspace_id": workspace_id}
        )

    async def find_first_by_form_id(
        self, form_id: str
    ) -> Optional[WorkspaceFormDocument]:
        """Any workspace's row for this form (imported forms can live in several)."""
        return await WorkspaceFormDocument.find_one({"form_id": form_id})

    async def list_in_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[WorkspaceFormDocument]:
        return await WorkspaceFormDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    @write_op
    async def save(
        self, workspace_form: WorkspaceFormDocument
    ) -> WorkspaceFormDocument:
        return await workspace_form.save()

    @write_op
    async def update(
        self, item_id: str, item: WorkspaceFormDocument
    ) -> WorkspaceFormDocument:
        workspace_form = await WorkspaceFormDocument.find_one(
            WorkspaceFormDocument.id == item_id
        )
        if not workspace_form:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in ")
        return await item.save()

    @write_op(replay=True)
    async def save_workspace_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user_id: str,
        workspace_form_settings: WorkspaceFormSettings,
    ) -> WorkspaceFormDocument:
        workspace_form = await WorkspaceFormDocument.find_one(
            {"workspace_id": workspace_id, "form_id": form_id, "user_id": user_id}
        )
        if not workspace_form:
            workspace_form = WorkspaceFormDocument(
                workspace_id=workspace_id,
                form_id=form_id,
                user_id=user_id,
            )
        workspace_form.settings = workspace_form_settings
        return await workspace_form.save()

    # TODO : Refactor this functions to include repo related only
    async def get_workspace_form_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        query: str,
        is_admin=True,
    ):
        try:
            query = {
                "workspace_id": workspace_id,
                "$or": [{"form_id": query}, {"settings.custom_url": query}],
            }
            if not is_admin:
                query["settings.private"] = False

            workspace_form = await WorkspaceFormDocument.find_one(query)
            return workspace_form
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_workspace_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        is_not_admin: bool = False,
        user: User = None,
        form_id: Optional[str] = None,
        form_id_or_slug: Optional[str] = None,
        pinned_only: bool = False,
        id_only: bool = False,
        filter_closed=False,
    ) -> List[Dict[str, Any]]:
        """Workspace-form rows a caller may see, as raw documents (``form_id``
        only with ``id_only``). ``form_id`` narrows to one form; ``form_id_or_slug``
        also accepts the form's custom URL. Anonymous visitors see public,
        unhidden forms; a signed-in non-member additionally sees private forms
        whose responder groups admit them (membership or the group's regex)."""
        try:
            query = {"workspace_id": workspace_id}
            if form_id is not None:
                query["form_id"] = form_id
            if form_id_or_slug is not None:
                query["$or"] = [
                    {"form_id": form_id_or_slug},
                    {"settings.custom_url": form_id_or_slug},
                ]
            if pinned_only:
                query["settings.pinned"] = True

            if not is_not_admin and user:
                visible = [
                    {"settings.hidden": False},
                    {"settings.hidden": {"$exists": False}},
                    {"user_id": user.id},
                ]
                if "$or" in query:
                    query["$and"] = [{"$or": query.pop("$or")}, {"$or": visible}]
                else:
                    query["$or"] = visible
            if is_not_admin and not user:
                query.setdefault("$and", []).extend(
                    [
                        {
                            "$or": [
                                {"settings.hidden": False},
                                {"settings.hidden": {"$exists": False}},
                            ]
                        },
                        {"settings.private": False},
                    ]
                )
            aggregation_pipeline = []

            if filter_closed:
                aggregation_pipeline.append(
                    {
                        "$match": {
                            "$or": [
                                {"settings.form_close_date": {"$exists": False}},
                                {"settings.form_close_date": ""},
                                {"settings.form_close_date": None},
                                {
                                    "settings.form_close_date": {
                                        "$gte": datetime.now(timezone.utc).isoformat()
                                    }
                                },
                            ]
                        }
                    }
                )
            if is_not_admin and user:
                aggregation_pipeline.extend(
                    [
                        {
                            "$lookup": {
                                "from": "responder_group_form",
                                "localField": "form_id",
                                "foreignField": "form_id",
                                "as": "groups_form",
                            }
                        },
                        {
                            "$lookup": {
                                "from": "responder_group_member",
                                "localField": "groups_form.group_id",
                                "foreignField": "group_id",
                                "as": "emails",
                            }
                        },
                        {
                            "$lookup": {
                                "from": "responder_group",
                                "localField": "groups_form.group_id",
                                "foreignField": "_id",
                                "as": "groups",
                            }
                        },
                        {"$set": {"regex": "$groups.regex"}},
                        {
                            "$unwind": {
                                "path": "$regex",
                                "preserveNullAndEmptyArrays": True,
                            }
                        },
                        {
                            "$match": {
                                "$and": [
                                    {
                                        "$or": [
                                            {"settings.hidden": False},
                                            {"settings.hidden": {"$exists": False}},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"settings.private": False},
                                            {"emails.identifier": user.sub},
                                            {
                                                "$and": [
                                                    {
                                                        "$expr": {
                                                            "$regexMatch": {
                                                                "input": user.sub,
                                                                "regex": "$regex",
                                                            }
                                                        }
                                                    },
                                                    {"regex": {"$ne": ""}},
                                                ]
                                            },
                                        ]
                                    },
                                ],
                            }
                        },
                    ]
                )
            if id_only:
                aggregation_pipeline.extend([{"$project": {"form_id": 1, "_id": 0}}])
            else:
                aggregation_pipeline.append(
                    {"$unset": ["groups_form", "emails", "groups", "regex"]}
                )
            workspace_forms = (
                await WorkspaceFormDocument.find(query)
                .aggregate(aggregation_pipeline)
                .to_list()
            )
            # the $unwind over group regexes yields one row per matching group
            seen, unique = set(), []
            for workspace_form in workspace_forms:
                key = workspace_form.get("_id", workspace_form.get("form_id"))
                if key not in seen:
                    seen.add(key)
                    unique.append(workspace_form)
            return unique
        except (InvalidURI, NetworkTimeout, OperationFailure, InvalidOperation):
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_form_ids_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        is_not_admin: bool = False,
        user: User = None,
        pinned_only: bool = False,
        form_id: Optional[str] = None,
        form_id_or_slug: Optional[str] = None,
        filter_closed: bool = False,
    ):
        workspace_forms = await self.get_workspace_forms_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=is_not_admin,
            user=user,
            form_id=form_id,
            form_id_or_slug=form_id_or_slug,
            pinned_only=pinned_only,
            id_only=True,
            filter_closed=filter_closed,
        )
        return list(set([a["form_id"] for a in workspace_forms]))

    async def get_workspace_form_with_custom_slug_form_id(
        self, workspace_id: PydanticObjectId, custom_url: str
    ):
        return await WorkspaceFormDocument.find_one(
            {
                "workspace_id": workspace_id,
                "$or": [{"form_id": custom_url}, {"settings.custom_url": custom_url}],
            }
        )

    async def get_workspace_ids_for_form_id(self, form_id):
        workspace_forms = await WorkspaceFormDocument.find(
            {"form_id": form_id}
        ).to_list()
        return [workspace_form.workspace_id for workspace_form in workspace_forms]

    @write_op
    async def delete_form_in_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        workspace_form = await WorkspaceFormDocument.find_one(
            {"form_id": form_id, "workspace_id": workspace_id}
        )
        if not workspace_form:
            raise HTTPException(status_code=404, content="Form not found in Workspace")
        await workspace_form.delete()
        return workspace_form

    async def check_is_form_imported_in_other_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        workspace_forms = await WorkspaceFormDocument.find(
            {"form_id": form_id}
        ).to_list()
        if len(workspace_forms) != 0:
            for workspace_form in workspace_forms:
                if workspace_form.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=HTTPStatus.CONFLICT,
                        content="Form has already been imported to another workspace",
                    )

    async def get_form_ids_imported_by_user(
        self, workspace_id: PydanticObjectId, user_id: str
    ):
        forms = await WorkspaceFormDocument.find(
            {"workspace_id": workspace_id, "user_id": user_id}
        ).to_list()
        return [form.form_id for form in forms]

    async def get_form_ids_in_workspaces_and_imported_by_user(
        self, workspace_ids: List[PydanticObjectId], user: User
    ):
        forms = await WorkspaceFormDocument.find(
            {
                "$or": [{"workspace_id": {"$in": workspace_ids}}, {"user_id": user.id}],
                "settings.provider": {"$ne": "self"},
            }
        ).to_list()
        return [form.form_id for form in forms]

    @write_op
    async def delete_forms(self, form_ids):
        return await WorkspaceFormDocument.find({"form_id": {"$in": form_ids}}).delete()

    async def get_workspace_forms_form_ids(self, form_ids: List[str]):
        return await WorkspaceFormDocument.find(
            {"form_id": {"$in": form_ids}}
        ).to_list()

    async def check_if_form_exists_in_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        # `and` between two Beanie expressions evaluated to the second only
        workspace_form = await WorkspaceFormDocument.find_one(
            {"workspace_id": workspace_id, "form_id": form_id}
        )
        return True if workspace_form is not None else False
