from beanie import PydanticObjectId

from backend.app.schemas.template import FormTemplateDocument


class FormTemplateRepository:

    async def get_templates(self, workspace_id: PydanticObjectId):
        return await FormTemplateDocument.find({"workspace_id": workspace_id}).aggregate([{
            "$set": {"id": "$_id"}
        }]).to_list()

    async def get_template_by_id(self, template_id: PydanticObjectId):
        return await FormTemplateDocument.find_one({"_id": template_id})

    async def import_template_to_workspace(self, workspace_id: PydanticObjectId, template_id: PydanticObjectId):
        template = await self.get_template_by_id(template_id)
        imported_template = FormTemplateDocument(**template.dict())
        imported_template.id = None
        imported_template.imported_from = template.workspace_id
        imported_template.workspace_id = workspace_id
        imported_template = await imported_template.save()
        return imported_template
