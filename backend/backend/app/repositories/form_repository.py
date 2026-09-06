from typing import List

from beanie import PydanticObjectId
from beanie.odm.enums import SortDirection
from beanie.odm.queries.aggregation import AggregationQuery
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import apaginate
from common.models.standard_form import StandardForm

from backend.app.exceptions import HTTPException
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.utils.aggregation_query_builder import create_filter_pipeline
from common.db.routing import write_op

# Arrays the $lookups leave behind once their values are folded into the
# document; nothing reads them and they can be large (every version of a form).
_LOOKUP_SCAFFOLDING = [
    "workspace_form",
    "form",
    "form_groups",
    "versions",
    "responses_deletion_requests",
]


class FormRepository:
    def _forms_in_workspace_query(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> AggregationQuery:
        aggregation_pipeline = [
            {
                "$lookup": {
                    "from": "workspace_forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "workspace_form",
                }
            },
            {"$unwind": "$workspace_form"},
            {"$match": {"workspace_form.workspace_id": workspace_id}},
            {
                "$set": {
                    "settings": "$workspace_form.settings",
                    "imported_by": "$workspace_form.user_id",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group_form",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form_groups",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group",
                    "localField": "form_groups.group_id",
                    "foreignField": "_id",
                    "as": "groups",
                }
            },
        ]

        aggregation_pipeline.extend(create_filter_pipeline(sort=sort))

        if is_admin:
            aggregation_pipeline.extend(
                [
                    {
                        "$lookup": {
                            "from": "form_responses",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "responses",
                        }
                    },
                    {
                        "$set": {
                            "responses": {
                                "$filter": {
                                    "input": "$responses",
                                    "as": "item",
                                    "cond": {
                                        "$ne": [{"$type": "$$item.answers"}, "missing"]
                                    },
                                }
                            }
                        }
                    },
                    {"$set": {"responses": {"$size": "$responses"}}},
                    {
                        "$lookup": {
                            "from": "responses_deletion_requests",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "responses_deletion_requests",
                        }
                    },
                    {
                        "$set": {
                            "deletion_requests": {
                                "$size": "$responses_deletion_requests"
                            }
                        }
                    },
                    {
                        "$lookup": {
                            "from": "form_versions",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "versions",
                        }
                    },
                    {"$set": {"is_published": {"$gt": [{"$size": "$versions"}, 0]}}},
                ]
            )
        aggregation_pipeline.append({"$unset": _LOOKUP_SCAFFOLDING})
        return FormDocument.find({"form_id": {"$in": form_id_list}}).aggregate(
            aggregation_pipeline
        )

    async def get_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> List[dict]:
        """Draft forms of a workspace with their workspace settings, importer,
        responder groups and — for admins — response/deletion counts and publish
        state. Raw documents, shaped for ``FormDtoCamelModel``."""
        return await self._forms_in_workspace_query(
            workspace_id, form_id_list, is_admin, sort
        ).to_list()

    async def paginate_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> Page:
        return await apaginate(
            self._forms_in_workspace_query(workspace_id, form_id_list, is_admin, sort)
        )

    def _published_forms_in_workspace_query(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ):
        aggregation_pipeline = [
            {"$sort": {"version": -1}},
            {"$group": {"_id": "$form_id", "latestVersion": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$latestVersion"}},
            {
                "$lookup": {
                    "from": "workspace_forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "workspace_form",
                }
            },
            {"$unwind": "$workspace_form"},
            {"$match": {"workspace_form.workspace_id": workspace_id}},
            {"$set": {"settings": "$workspace_form.settings", "is_published": True}},
            {
                "$lookup": {
                    "from": "form_responses",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "responses",
                }
            },
            {
                "$set": {
                    "responses": {
                        "$filter": {
                            "input": "$responses",
                            "as": "item",
                            "cond": {"$ne": [{"$type": "$$item.answers"}, "missing"]},
                        }
                    }
                }
            },
            {"$set": {"responses": {"$size": "$responses"}}},
            {
                "$lookup": {
                    "from": "responses_deletion_requests",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "responses_deletion_requests",
                }
            },
            {"$set": {"deletion_requests": {"$size": "$responses_deletion_requests"}}},
        ]
        get_action_aggregation = [
            {
                "$lookup": {
                    "from": "forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form",
                }
            },
            {"$unwind": "$form"},
            {
                "$set": {
                    "actions": "$form.actions",
                    "parameters": "$form.parameters",
                    "secrets": "$form.secrets",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group_form",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form_groups",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group",
                    "localField": "form_groups.group_id",
                    "foreignField": "_id",
                    "as": "groups",
                }
            },
        ]
        if get_actions:
            aggregation_pipeline.extend(get_action_aggregation)
        aggregation_pipeline.extend(create_filter_pipeline(sort=sort))
        aggregation_pipeline.append({"$unset": _LOOKUP_SCAFFOLDING})
        return FormVersionsDocument.find({"form_id": {"$in": form_id_list}}).aggregate(
            aggregation_pipeline=aggregation_pipeline
        )

    async def get_published_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ) -> List[dict]:
        """Latest published version of each form, with workspace settings and
        response/deletion counts; ``get_actions`` adds the draft's actions,
        parameters, secrets and responder groups."""
        return await self._published_forms_in_workspace_query(
            workspace_id, form_id_list, sort, get_actions
        ).to_list()

    async def paginate_published_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ) -> Page:
        return await apaginate(
            self._published_forms_in_workspace_query(
                workspace_id, form_id_list, sort, get_actions
            )
        )

    async def search_form_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_ids: List[str],
        query: str,
        published: bool = False,
    ):
        query_document = FormDocument
        if published:
            query_document = FormVersionsDocument

        aggregation_pipeline = [
            {
                "$lookup": {
                    "from": "workspace_forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "workspace_form",
                }
            },
            {"$unwind": "$workspace_form"},
            {"$match": {"workspace_form.workspace_id": workspace_id}},
            {
                "$set": {
                    "settings": "$workspace_form.settings",
                    "imported_by": "$workspace_form.user_id",
                }
            },
        ]

        if published:
            aggregation_pipeline.extend(
                [
                    {"$sort": {"version": -1}},
                    {
                        "$group": {
                            "_id": "$form_id",
                            "latestVersion": {"$first": "$$ROOT"},
                        }
                    },
                    {"$replaceRoot": {"newRoot": "$latestVersion"}},
                ]
            )
        if not published:
            aggregation_pipeline.extend(
                [
                    {
                        "$lookup": {
                            "from": "form_versions",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "versions",
                        }
                    },
                    {"$set": {"is_published": {"$gt": [{"$size": "$versions"}, 0]}}},
                ]
            )

        aggregation_pipeline.append({"$sort": {"created_at": -1}})
        aggregation_pipeline.append({"$unset": _LOOKUP_SCAFFOLDING})
        return (
            await query_document.find(
                {
                    "form_id": {"$in": form_ids},
                    "$or": [
                        {"title": {"$regex": query, "$options": "i"}},
                        {"description": {"$regex": query, "$options": "i"}},
                    ],
                }
            )
            .aggregate(aggregation_pipeline=aggregation_pipeline)
            .to_list()
        )

    @write_op
    async def save_form(self, form: FormDocument):
        return await form.save()

    @write_op
    async def save_form_version(
        self, form_version: FormVersionsDocument
    ) -> FormVersionsDocument:
        return await form_version.save()

    @write_op
    async def delete_versions_by_imported_form_id(self, imported_form_id: str):
        return await FormVersionsDocument.find(
            {"imported_form_id": imported_form_id}
        ).delete()

    async def get_forms_by_form_ids(self, form_ids: List[str]) -> List[FormDocument]:
        return await FormDocument.find({"form_id": {"$in": form_ids}}).to_list()

    @write_op
    async def delete_form(self, form_id: str):
        form = await FormDocument.find_one({"form_id": form_id})
        if not form:
            raise HTTPException(status_code=404, content="Form not found")
        return await form.delete()

    @write_op
    async def delete_forms(self, form_ids: List[str]):
        return await FormDocument.find({"form_id": {"$in": form_ids}}).delete()

    @write_op(replay=True)
    async def create_form(self, form: StandardForm) -> FormDocument:
        form_document = FormDocument(**form.model_dump(mode="json"))
        return await form_document.save()

    @write_op
    async def update_form(self, form_id: PydanticObjectId, form: StandardForm):
        form_document = await FormDocument.find_one({"form_id": str(form_id)})
        form_document.fields = form.fields
        # None means "the client didn't send hidden fields" (e.g. an older
        # webapp bundle) — preserve what's stored. An explicit [] clears them.
        if form.hidden_fields is not None:
            form_document.hidden_fields = form.hidden_fields
        form_document.title = form.title
        form_document.logo = form.logo
        form_document.cover_image = form.cover_image
        form_document.description = form.description
        form_document.welcome_page = form.welcome_page
        form_document.thankyou_page = form.thankyou_page
        form_document.theme = form.theme
        form_document.consent = form.consent if form.consent else form_document.consent
        form_document.settings = (
            form.settings if form.settings else form_document.settings
        )
        return await form_document.save()

    async def get_form_document_by_id(self, form_id: str):
        return await FormDocument.find_one({"form_id": form_id})

    async def get_latest_version_of_form(self, form_id: PydanticObjectId):
        return (
            await FormVersionsDocument.find({"form_id": str(form_id)})
            .sort(("version", SortDirection.DESCENDING))
            .first_or_none()
        )

    async def get_form_by_by_version(
        self, form_id: PydanticObjectId, version: FormVersion | int
    ):
        if version == FormVersion.latest:
            return await self.get_latest_version_of_form(form_id=form_id)
        # form_id arrives as an ObjectId; the field is stored as its string
        return await FormVersionsDocument.find_one(
            {"form_id": str(form_id), "version": version}
        )

    @write_op(replay=True)
    async def publish_form(self, form: FormDocument, version: int):
        new_form_version = FormVersionsDocument(
            **form.model_dump(mode="json"), version=version
        )
        new_form_version.id = None
        return await new_form_version.save()

    async def get_form_by_id(self, form_id: PydanticObjectId):
        return await FormDocument.find_one({"form_id": str(form_id)})

    @write_op
    async def update_form_actions(
        self,
        form_id: PydanticObjectId,
        action_id: PydanticObjectId,
        form: StandardForm,
        payload: FormActionsDto,
    ):
        # Accessing secrets using the action_id
        secrets = form.secrets[str(action_id)]

        # Update the secret for that action_id
        for secret in secrets:
            if secret.name == payload.name:
                secret.value = payload.value

        form.secrets[str(action_id)] = secrets

        return await form.save()
