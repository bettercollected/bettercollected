from common.ids import RecordId
from classy_fastapi import Routable, post, patch
from fastapi import Depends
from pydantic import BaseModel, Field, field_validator

from backend.app.container import container
from backend.app.router import router
from backend.app.services.user_service import get_api_key, get_logged_admin
from backend.app.models.dtos.form_actions_dto import FormActionsDto


class CopyRecipientQuery(BaseModel):
    # one address: no longer than an address can be, and not blank
    address: str = Field(max_length=254)

    @field_validator("address")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("address must not be blank")
        return value


@router(
    prefix="/temporal",
    tags=["Temporal Router"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Authorization token is missing."},
        403: {"description": "You are not allowed to perform this action."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class TemporalRouter(Routable):
    def __init__(
        self,
        form_schedular=container.form_schedular(),
        form_actions_service=container.form_actions_service(),
        copy_recipient_service=container.copy_recipient_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.form_schedular = form_schedular
        self.form_actions_service = form_actions_service
        self.copy_recipient_service = copy_recipient_service

    @patch("/forms/{form_id}/actions/{action_id}/secrets")
    async def patch_form_secrets(
        self,
        form_id: RecordId,
        action_id: RecordId,
        payload: FormActionsDto,
        api_key=Depends(get_api_key),
    ):
        await self.form_actions_service.update_form_secrets(form_id, action_id, payload)
        # never echo the form back: it carries every action's secrets
        return "Updated"

    @post("/workspaces/{workspace_id}/forms/{form_id}/copy-recipient")
    async def check_copy_recipient(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        payload: CopyRecipientQuery,
        api_key=Depends(get_api_key),
    ):
        """The actions executor asks, right before a "send me a copy" mail,
        whether the address may still receive it (a member of the workspace
        who is still enabled, the form's creator included, as of now). Only a yes or no goes back, never
        who the members are."""
        allowed = await self.copy_recipient_service.is_allowed(
            payload.address, workspace_id, form_id
        )
        return {"allowed": allowed}

    @post("/delete/submissions/{submission_id}")
    async def delete_expired_submissions(
        self, submission_id: str, api_key=Depends(get_api_key)
    ):
        return await self.form_schedular.delete_response(submission_id=submission_id)
