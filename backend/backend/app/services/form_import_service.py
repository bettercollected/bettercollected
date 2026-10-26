import datetime
import json
from typing import Any, Dict

from beanie import PydanticObjectId

from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.workspace import WorkspaceResponseDto
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.repositories.response_scope import response_scope
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDocument,
)
from backend.app.services.form_service import FormService
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm, StandardFormResponseAnswer
from common.services.crypto_service import crypto_service


class FormImportService:
    def __init__(
        self,
        form_service: FormService,
        workspace_repo: PostgresWorkspaceRepository,
        form_response_repo: PostgresFormResponseRepository,
        workspace_form_repo=None,
    ):
        self.form_service = form_service
        self._workspace_repo = workspace_repo
        self._form_response_repo = form_response_repo
        self._workspace_form_repo = workspace_form_repo  # routed

    async def get_form_workspace_by_id(self, workspace_id: PydanticObjectId):
        return await self._workspace_repo.get_workspace_by_id(workspace_id=workspace_id)

    async def save_converted_form_and_responses(
        self,
        response_data: Dict[str, Any],
        form_response_data_owner: str,
        workspace_id: PydanticObjectId,
    ) -> StandardForm | None:
        form_data = FormImportResponse.model_validate(response_data)
        if not (form_data.form or form_data.responses):
            return None
        if not workspace_id:
            # responses belong to the workspace they are imported into (#768)
            raise ValueError("An import needs the workspace it goes into.")
        standard_form = await self.form_service.save_form(form_data.form)
        # The responses are this workspace's copy (#768): the same provider
        # form may be linked to other workspaces, each with its own.
        scope = await response_scope(
            self._workspace_form_repo, workspace_id, [standard_form.form_id]
        )
        # a re-import updates the workspace's stored copy of each response
        # instead of adding another
        stored_ids = {
            stored.response_id: stored.id
            for stored in await self._form_response_repo.list_by_form_id(scope)
        }
        # A deletion request completed in this workspace (by staff, or by
        # deleting the response) is not undone by a sync: the response stays
        # deleted here even while the source still has it.
        deleted_here = {
            request.response_id
            for request in await self._form_response_repo.list_deletion_requests_for_form_ids(
                scope
            )
            if request.status == DeletionRequestStatus.SUCCESS
        }
        responses = form_data.responses
        updated_responses_id = []
        for response in responses:
            if response.response_id in deleted_here:
                continue
            response_document = FormResponseDocument(**response.model_dump(mode="json"))
            response_document.id = stored_ids.get(response.response_id)
            response_document.form_id = standard_form.form_id
            response_document.workspace_id = PydanticObjectId(workspace_id)
            data_owner_answer = response_document.answers.get(form_response_data_owner)

            if not response_document.dataOwnerIdentifier:
                response_document.dataOwnerIdentifier = (
                    data_owner_answer.text
                    or data_owner_answer.email
                    or data_owner_answer.phone_number
                    or data_owner_answer.number
                    if data_owner_answer
                    else None
                )
            if workspace_id:
                for k, v in response_document.answers.items():
                    if isinstance(v, StandardFormResponseAnswer):
                        response_document.answers[k] = v.model_dump()
                response_document.answers = crypto_service.encrypt(
                    workspace_id=workspace_id,
                    form_id=response_document.form_id,
                    data=json.dumps(response_document.answers),
                )
            await self._form_response_repo.save(response_document)
            updated_responses_id.append(response.response_id)

        await self._form_response_repo.delete_by_form_id_except(
            scope, updated_responses_id
        )

        modified_count = (
            await self._form_response_repo.mark_deletion_requests_success_except(
                scope=scope,
                provider=standard_form.settings.provider,
                # the skipped ones are already done: not counted again
                keep_response_ids=updated_responses_id + sorted(deleted_here),
                now=datetime.datetime.now(datetime.timezone.utc),
            )
        )
        if modified_count >= 1:
            workspace = await self._workspace_repo.get_workspace_by_id(
                workspace_id=workspace_id
            )
            await self.form_service.user_tags_service.add_user_tag(
                user_id=WorkspaceResponseDto(
                    **workspace.model_dump(mode="json")
                ).owner_id,
                tag=UserTagType.DELETION_REQUEST_PROCESSED,
            )
        return standard_form
