from http import HTTPStatus
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from common.constants import MESSAGE_NOT_FOUND
from common.models.user import User
from backend.app.exceptions import HTTPException
from backend.app.models.template import StandardFormTemplate, StandardTemplateSetting
from backend.app.schemas.template import FormTemplateDocument
from common.db.routing import write_op


async def with_origin_titles(
    workspaces, templates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """``templates`` (stored template documents) as the listings return them:
    ``id`` set, and ``imported_from`` (the id of the workspace a template was
    imported from) replaced by that workspace's title, or left out when the
    workspace no longer exists. The workspaces are read through
    ``workspaces`` (the identity group's repository): in 4.0 this was a
    ``$lookup`` into ``workspaces``, which both template repositories now
    compose instead (a join across groups finds nothing once the joined
    group leaves Mongo)."""
    origins = {
        t["imported_from"] for t in templates if t.get("imported_from") is not None
    }
    titles = {}
    if origins:
        for workspace in await workspaces.get_workspace_by_ids(list(origins)):
            titles[workspace.id] = workspace.title
    for template in templates:
        template["id"] = template["_id"]
        # $lookup + $unwind(preserveNull) + $set imported_from: "$workspace.title"
        origin = template.get("imported_from")
        if origin is not None and origin in titles:
            template["imported_from"] = titles[origin]
        else:
            template.pop("imported_from", None)
    return templates


class FormTemplateRepository:
    def __init__(self, workspace_repository=None):
        # the workspace repository: the titles of the workspaces templates
        # were imported from (get_templates_with_creator)
        self._workspaces = workspace_repository

    async def get_templates_with_creator(
        self,
        v2: Optional[bool] = None,
        workspace_id: PydanticObjectId = None,
        template_id: PydanticObjectId = None,
        predefined_workspace: bool = False,
    ):
        query = {"workspace_id": workspace_id}
        if predefined_workspace:
            query["settings.is_public"] = True
        if template_id:
            query["_id"] = template_id

        pipeline = [
            {
                "$match": {
                    "$or": (
                        [{"builder_version": "v2"}]
                        if v2
                        else [
                            {
                                "$or": [
                                    {"builder_version": {"$ne": "v2"}},
                                    {"builder_version": {"$exists": False}},
                                    {"builder_version": None},
                                ]
                            }
                        ]
                    )
                }
            },
            {"$sort": {"created_at": -1}},
        ]
        templates = (
            await FormTemplateDocument.find(query).aggregate(pipeline).to_list()
        )
        return await with_origin_titles(self._workspaces, templates)

    async def get_template_by_id(self, template_id: PydanticObjectId):
        return await FormTemplateDocument.find_one({"_id": template_id})

    async def get_v2_template_by_title(
        self, title: str
    ) -> Optional[FormTemplateDocument]:
        """The first flow-builder (v2) template with this title, in any
        workspace (the flow-template seed's existence check)."""
        return await FormTemplateDocument.find_one(
            {"title": title, "builder_version": "v2"}
        )

    async def get_template_by_workspace_id_n_template_id(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId
    ):
        return await FormTemplateDocument.find_one(
            {"_id": template_id, "workspace_id": workspace_id}
        )

    async def get_template_by_id_with_creator(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId
    ):
        templates = await self.get_templates_with_creator(
            workspace_id=workspace_id, template_id=template_id
        )

        if len(templates) > 0:
            return templates[0]

        raise HTTPException(HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)

    @write_op(replay=True)
    async def import_template_to_workspace(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId
    ):
        template = await self.get_template_by_id(template_id)
        imported_template = FormTemplateDocument(**template.model_dump(mode="json"))
        imported_template.id = None
        imported_template.imported_from = template.workspace_id
        imported_template.workspace_id = workspace_id
        imported_template.settings = StandardTemplateSetting()
        imported_template = await imported_template.save()
        return imported_template

    @write_op(replay=True)
    async def create_new_template(
        self,
        workspace_id: PydanticObjectId,
        template_body: StandardFormTemplate,
        user: User,
    ):
        template = FormTemplateDocument(**template_body.model_dump(mode="json"))
        template.workspace_id = workspace_id
        template.created_by = user.id
        return await template.save()

    @write_op
    async def update_template(
        self, template_id: PydanticObjectId, template_body: StandardFormTemplate
    ):
        template = await FormTemplateDocument.find_one({"_id": template_id})
        template.fields = template_body.fields
        template.settings = template_body.settings
        template.title = template_body.title
        template.description = template_body.description
        template.button_text = template_body.button_text
        template.logo = template_body.logo
        template.cover_image = template_body.cover_image
        return await template.save()

    @write_op
    async def save(self, template: FormTemplateDocument) -> FormTemplateDocument:
        return await template.save()

    @write_op
    async def delete_template(self, template_id: PydanticObjectId):
        template = await FormTemplateDocument.find_one({"_id": template_id})
        if not template:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Template not found")
        await template.delete()
        return str(template_id)
