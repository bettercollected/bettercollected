from beanie import PydanticObjectId

from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.schemas.consent import WorkspaceConsentDocument


class WorkspaceConsentRepo:
    async def get_workspace_consents(self, workspace_id: PydanticObjectId):
        return await WorkspaceConsentDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    async def create_workspace_consent(
        self, workspace_id: PydanticObjectId, consent: ConsentCamelModel
    ):
        consent_document = WorkspaceConsentDocument(**consent.dict())
        consent_document.workspace_id = workspace_id
        return await consent_document.save()
