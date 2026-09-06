from beanie import PydanticObjectId

from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.schemas.consent import WorkspaceConsentDocument
from common.db.routing import write_op


class WorkspaceConsentRepo:
    async def get_workspace_consents(self, workspace_id: PydanticObjectId):
        return await WorkspaceConsentDocument.find(
            {"workspace_id": workspace_id}
        ).to_list()

    @write_op(replay=True)
    async def create_workspace_consent(
        self, workspace_id: PydanticObjectId, consent: ConsentCamelModel
    ):
        consent_document = WorkspaceConsentDocument(**consent.model_dump(mode="json"))
        consent_document.workspace_id = workspace_id
        return await consent_document.save()
