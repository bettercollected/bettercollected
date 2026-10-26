import json
from typing import List

from common.ids import RecordId
from classy_fastapi import Routable, post, get, patch, delete
from http import HTTPStatus

from fastapi import Depends, UploadFile, Form
from pydantic import ValidationError
from common.models.user import User
from typing import Optional
from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dataclasses.user_tokens import UserTokens
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.template import (
    StandardFormTemplateCamelModel,
    StandardFormTemplateResponse,
    StandardFormTemplateResponseCamelModel,
    StandardTemplateSettingsCamelModel,
)
from backend.app.router import router
from backend.app.services.template_service import FormTemplateService
from backend.app.services.user_service import (
    get_logged_user,
    get_user_if_logged_in,
    get_api_key,
    get_access_token,
    get_refresh_token,
)
from backend.app.services.workspace_form_service import WorkspaceFormService


from backend.app.services.user_service import get_full_user  # noqa: E402

def template_from_form_body(body: str) -> StandardFormTemplateCamelModel:
    """The template a multipart ``template_body`` describes; a 422 naming the
    invalid fields (never their values) when it doesn't fit the model."""
    try:
        return StandardFormTemplateCamelModel(**json.loads(body))
    except (ValidationError, ValueError, TypeError) as error:
        places = (
            sorted({".".join(str(p) for p in e["loc"]) for e in error.errors()})
            if isinstance(error, ValidationError)
            else []
        )
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            content="The template is not valid"
            + (f": {', '.join(places)}." if places else "."),
        )


@router(
    prefix="",
    tags=["Form Templates"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Authorization token is missing."},
        403: {"description": "You are not allowed to perform this action."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class FormTemplateRouter(Routable):
    def __init__(
        self,
        workspace_form_service: WorkspaceFormService = container.workspace_form_service(),
        form_template_service: FormTemplateService = container.form_template_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.workspace_form_service = workspace_form_service
        self.form_template_service = form_template_service

    @get("/templates", response_model=List[StandardFormTemplateResponseCamelModel])
    async def get_templates(
        self,
        v2: Optional[bool] = False,
        workspace_id: Optional[RecordId] = None,
        user: User = Depends(get_full_user),
    ):
        form_templates = await self.form_template_service.get_templates(
            v2, workspace_id, user
        )
        return [
            StandardFormTemplateResponseCamelModel(**form_template)
            for form_template in form_templates
        ]

    @get("/templates/{template_id}", response_model=StandardFormTemplateCamelModel)
    async def get_template_by_id(
        self,
        template_id: RecordId,
        workspace_id: RecordId = None,
        user: User = Depends(get_user_if_logged_in),
    ):
        response = await self.form_template_service.get_template_by_id(
            workspace_id=workspace_id, user=user, template_id=template_id
        )
        return StandardFormTemplateCamelModel(**response.model_dump(mode='json'))

    @patch("/template/{template_id}/preview")
    async def patch_template_preview_image(
        self,
        template_id: RecordId,
        preview_image: UploadFile = None,
        api_key=Depends(get_api_key),
    ):
        response = await self.form_template_service.update_template_preview(
            template_id=template_id,
            preview_image=preview_image,
        )
        return response

    @post("/workspaces/{workspace_id}/form/{form_id}/template")
    async def create_template_from_form(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        user: User = Depends(get_full_user),
        access_token=Depends(get_access_token),
        refresh_token=Depends(get_refresh_token),
    ):
        user_tokens = UserTokens(access_token=access_token, refresh_token=refresh_token)
        response = await self.workspace_form_service.duplicate_form(
            workspace_id=workspace_id,
            form_id=form_id,
            is_template=True,
            user=user,
            user_tokens=user_tokens,
        )
        return StandardFormTemplateResponse(**response.model_dump(mode='json'))

    @post(
        "/workspaces/{workspace_id}/template",
        response_model=StandardFormTemplateResponse,
    )
    async def create_new_template(
        self,
        workspace_id: RecordId,
        template_body: str = Form(),
        logo: UploadFile = None,
        cover_image: UploadFile = None,
        user: User = Depends(get_full_user),
    ):
        template = template_from_form_body(template_body)
        response = await self.form_template_service.create_new_template(
            workspace_id=workspace_id,
            user=user,
            template_body=template,
            logo=logo,
            cover_image=cover_image,
        )
        return StandardFormTemplateResponse(**response.model_dump(mode='json'))

    @post(
        "/workspaces/{workspace_id}/template/{template_id}/import",
        response_model=StandardFormTemplateCamelModel,
    )
    async def import_template_to_workspace(
        self,
        workspace_id: RecordId,
        template_id: RecordId,
        user: User = Depends(get_full_user),
    ):
        response = await self.form_template_service.import_form_template_to_workspace(
            workspace_id, user, template_id
        )
        return StandardFormTemplateCamelModel(**response.model_dump(mode='json'))

    @post(
        "/workspaces/{workspace_id}/template/{template_id}",
        response_model=FormDtoCamelModel,
    )
    async def create_form_from_template(
        self,
        workspace_id: RecordId,
        template_id: RecordId,
        user: User = Depends(get_full_user),
    ):
        response = await self.form_template_service.create_form_from_template(
            workspace_id=workspace_id, template_id=template_id, user=user
        )
        return response

    @patch(
        "/workspaces/{workspace_id}/template/{template_id}",
        response_model=StandardFormTemplateCamelModel,
    )
    async def update_template(
        self,
        workspace_id: RecordId,
        template_id: RecordId,
        logo: UploadFile = None,
        cover_image: UploadFile = None,
        template_body: str = Form(),
        user: User = Depends(get_full_user),
        access_token=Depends(get_access_token),
        refresh_token=Depends(get_refresh_token),
    ):
        template = template_from_form_body(template_body)
        response = await self.form_template_service.update_template(
            workspace_id=workspace_id,
            template_id=template_id,
            user=user,
            template_body=template,
            logo=logo,
            cover_image=cover_image,
            user_tokens=UserTokens(
                access_token=access_token, refresh_token=refresh_token
            ),
        )
        return response

    @patch(
        "/workspaces/{workspace_id}/template/{template_id}/settings",
        response_model=StandardFormTemplateCamelModel,
    )
    async def update_template_settings(
        self,
        workspace_id: RecordId,
        template_id: RecordId,
        settings: StandardTemplateSettingsCamelModel,
        user: User = Depends(get_full_user),
    ):
        return await self.form_template_service.update_template_settings(
            workspace_id=workspace_id,
            template_id=template_id,
            settings=settings,
            user=user,
        )

    @delete("/workspaces/{workspace_id}/template/{template_id}")
    async def delete_template(
        self,
        workspace_id: RecordId,
        template_id: RecordId,
        user: User = Depends(get_full_user),
    ):
        response = await self.form_template_service.delete_template(
            workspace_id=workspace_id, template_id=template_id, user=user
        )
        return response
