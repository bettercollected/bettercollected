import json
from http import HTTPStatus

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, patch, post, delete
from common.constants import MESSAGE_UNAUTHORIZED
from common.models.consent import ResponseRetentionType
from common.models.form_import import FormImportRequestBody
from common.models.standard_form import StandardForm, Trigger
from common.models.user import User
from fastapi import Depends, UploadFile, Form
from fastapi_pagination import Page
from loguru import logger
from starlette.requests import Request

from backend.app.container import container
from backend.app.decorators.user_tag_decorators import user_tag
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import AddActionToFormDto, UpdateActionInFormDto
from backend.app.models.dtos.worksapce_form_dto import GroupsDto
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.request_dtos import CreateFormWithAI
from backend.app.models.dtos.response_dtos import (
    WorkspaceFormPatchResponse,
    StandardFormCamelModel,
    StandardFormResponseCamelModel,
    FormFileResponse,
)
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.models.dtos.worksapce_form_dto import GroupsDto
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.router import router
from backend.app.services.form_service import FormService
from backend.app.services.openai_service import OpenAIService
from backend.app.services.temporal_service import TemporalService
from backend.app.services.user_service import (
    get_logged_user,
    get_user_if_logged_in,
    get_api_key,
)
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.config import settings


@router(
    prefix="/workspaces/{workspace_id}/forms",
    tags=["Workspace Forms"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class WorkspaceFormsRouter(Routable):
    def __init__(
        self,
        form_service: FormService = container.form_service(),
        temporal_service: TemporalService = container.temporal_service(),
        workspace_form_service: WorkspaceFormService = container.workspace_form_service(),
        open_ai_service=container.openai_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_service = form_service
        self._temporal_service = temporal_service
        self.workspace_form_service = workspace_form_service
        self.open_ai_service: OpenAIService = open_ai_service

    @get("", response_model=Page[FormDtoCamelModel])
    async def get_workspace_forms(
        self,
        workspace_id: PydanticObjectId,
        sort: SortRequest = Depends(),
        user: User = Depends(get_user_if_logged_in),
        published: bool = False,
        pinned_only: bool = False,
    ) -> Page[FormDtoCamelModel]:
        if not user and not published:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content=MESSAGE_UNAUTHORIZED
            )
        forms = await self._form_service.get_forms_in_workspace(
            workspace_id=workspace_id,
            sort=sort,
            published=published,
            pinned_only=pinned_only,
            user=user,
        )
        return forms

    @post(
        "",
        response_model=FormDtoCamelModel,
    )
    async def create_form(
        self,
        workspace_id: PydanticObjectId,
        form_body: str = Form(),
        logo: UploadFile = None,
        cover_image: UploadFile = None,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

        form = json.loads(form_body)

        minified_form = FormDtoCamelModel(**form)
        # Camel model is converted to basic modal so that camel case is not stored in db
        response = await self.workspace_form_service.create_form(
            workspace_id=workspace_id,
            form=StandardForm(**minified_form.dict()),
            user=user,
            logo=logo,
            cover_image=cover_image,
        )
        return FormDtoCamelModel(**response.dict())

    @post("/ai")
    async def create_form_with_ai(
        self,
        workspace_id: PydanticObjectId,
        create_form: CreateFormWithAI,
        user=Depends(get_logged_user),
    ):
        return await self.open_ai_service.create_form_with_ai(
            workspace_id=workspace_id, create_form_ai=create_form, user=user
        )

    @post("/search")
    async def search_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        query: str,
        published: bool = False,
        user: User = Depends(get_user_if_logged_in),
    ):
        if not user and not published:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content=MESSAGE_UNAUTHORIZED
            )
        forms = await self._form_service.search_form_in_workspace(
            workspace_id=workspace_id, query=query, published=published, user=user
        )
        return forms

    @get(
        "/{form_id}",
        response_model=FormDtoCamelModel,
    )
    async def _get_form_by_id(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        published: bool = False,
        user: User = Depends(get_user_if_logged_in),
        draft: bool = False,
    ):
        if not user and not published:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content=MESSAGE_UNAUTHORIZED
            )
        form = await self._form_service.get_form_by_id(
            workspace_id=workspace_id,
            form_id=form_id,
            published=published,
            user=user,
            draft=draft,
        )
        return form

    @patch(
        "/{form_id}",
        response_model=FormDtoCamelModel,
    )
    async def patch_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        form_body: str = Form(),
        logo: UploadFile = None,
        cover_image: UploadFile = None,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

        form = json.loads(form_body)

        minified_form = FormDtoCamelModel(**form)
        # Camel model is converted to basic modal so that camel case is not stored in db
        response = await self.workspace_form_service.update_form(
            workspace_id=workspace_id,
            form_id=form_id,
            form=StandardForm(**minified_form.dict()),
            user=user,
            logo=logo,
            cover_image=cover_image,
        )
        return StandardFormCamelModel(**response.dict())

    @post("/{form_id}/duplicate", response_model=FormDtoCamelModel)
    async def duplicate_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

        response = await self.workspace_form_service.duplicate_form(
            workspace_id=workspace_id, form_id=form_id, user=user
        )
        return StandardFormCamelModel(**response.dict())

    @post("/{form_id}/publish", response_model=FormDtoCamelModel)
    async def publish_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        form = await self.workspace_form_service.publish_form(
            workspace_id=workspace_id, form_id=form_id, user=user
        )
        form_dict = form.dict()
        form_dict["form_id"] = str(form_id)
        return StandardFormCamelModel(**form_dict)

    @post("/{form_id}/response")
    async def respond_to_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        request: Request,
        files: list[UploadFile] = None,
        file_field_ids: list[str] = Form(None),
        file_ids: list[str] = Form(None),
        response: str = Form(None),
        user: User = Depends(get_user_if_logged_in),
    ):
        form_files = None
        if files and file_field_ids and file_ids:
            form_files = [
                FormFileResponse(
                    file_id=file_id,
                    field_id=field_id,
                    filename=file.filename,
                    file=file,
                )
                for file_id, field_id, file in zip(file_ids, file_field_ids, files)
            ]
        parsed_response = StandardFormResponseCamelModel(**json.loads(response))
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
        response = await self.workspace_form_service.submit_response(
            workspace_id=workspace_id,
            form_id=form_id,
            response=parsed_response,
            form_files=form_files,
            user=user,
        )
        if parsed_response.expiration_type not in [ResponseRetentionType.FOREVER, None]:
            await self._temporal_service.add_scheduled_job_for_deleting_response(
                response=response
            )
            logger.info("Add job for deletion response: " + response.response_id)
        return response.submission_uuid

    @patch("/{form_id}/response/{response_id}")
    async def patch_form_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response_id: PydanticObjectId,
        files: list[UploadFile] = None,
        file_field_ids: list[str] = Form(None),
        file_ids: list[str] = Form(None),
        response: str = Form(None),
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

        form_files = None
        if files and file_field_ids and file_ids:
            form_files = [
                FormFileResponse(
                    file_id=file_id,
                    field_id=field_id,
                    filename=file.filename,
                    file=file,
                )
                for file_id, field_id, file in zip(file_ids, file_field_ids, files)
            ]
        parsed_response = StandardFormResponseCamelModel(**json.loads(response))
        return await self.workspace_form_service.patch_response(
            workspace_id=workspace_id,
            form_id=form_id,
            response_id=response_id,
            form_files=form_files,
            response=parsed_response,
            user=user,
        )

    @delete(
        "/{form_id}/response/{response_id}",
    )
    async def delete_form_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response_id: str,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
        return await self.workspace_form_service.delete_form_response(
            workspace_id=workspace_id,
            form_id=form_id,
            response_id=response_id,
            user=user,
        )

    @get("/{form_id}/versions/{version}", response_model=FormDtoCamelModel)
    async def get_form_with_version(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        version: FormVersion | int,
        user: User = Depends(get_user_if_logged_in),
    ):
        return await self._form_service.get_form_by_version(
            workspace_id=workspace_id, form_id=form_id, version=version, user=user
        )

    @patch(
        "/{form_id}/settings",
    )
    async def patch_settings_for_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        settings: SettingsPatchDto,
        user: User = Depends(get_logged_user),
    ):
        workspace = await self.workspace_form_service.get_form_workspace_by_id(
            workspace_id
        )
        if not workspace.is_pro and settings.disable_branding is not None:
            return HTTPException(403, "You are forbidden to perform this action")

        data = await self._form_service.patch_settings_in_workspace_form(
            workspace_id, form_id, settings, user
        )
        return WorkspaceFormPatchResponse(**data.dict())

    @patch(
        "/{form_id}/groups/add",
        summary="Add form in group",
    )
    @user_tag(tag=UserTagType.FORM_ADDED_TO_GROUP)
    async def patch_groups_for_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        groups: GroupsDto,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.add_groups_to_form(
            workspace_id, form_id, groups.group_ids, user
        )

    @delete(
        "/{form_id}/groups",
        summary="Delete form from group",
    )
    async def delete_group_from_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        group_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.delete_group_from_form(
            workspace_id=workspace_id, form_id=form_id, group_id=group_id, user=user
        )

    @post(
        "/import/{provider}",
    )
    @user_tag(tag=UserTagType.FORM_IMPORTED)
    async def _import_form_to_workspace(
        self,
        workspace_id: PydanticObjectId,
        provider: str,
        form: FormImportRequestBody,
        request: Request,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.import_form_to_workspace(
            workspace_id, provider, form, user, request
        )

    @delete(
        "/{form_id}",
        responses={
            404: {"description": "Bad Request"},
        },
    )
    async def _delete_form_from_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.delete_form_from_workspace(
            workspace_id=workspace_id, form_id=form_id, user=user
        )

    @post("/{form_id}/actions")
    async def _add_action_to_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        add_action_to_form_params: AddActionToFormDto,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.add_action_to_form(
            workspace_id=workspace_id,
            form_id=form_id,
            add_action_to_form_params=add_action_to_form_params,
            user=user,
        )

    @patch("/{form_id}/actions")
    async def update_form_actions(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        update_action_dto: UpdateActionInFormDto,
        user: User = Depends(get_logged_user),
    ):
        await self.workspace_form_service.update_action_status_in_form(
            workspace_id=workspace_id,
            form_id=form_id,
            update_action_dto=update_action_dto,
            user=user,
        )
        return "Updated"

    @delete("/{form_id}/actions/{action_id}")
    async def _remove_action_from_form(
        self,
        workspace_id: PydanticObjectId,
        action_id: PydanticObjectId,
        form_id: PydanticObjectId,
        trigger: Trigger = Trigger.on_submit,
        user: User = Depends(get_logged_user),
    ):
        updated_actions = await self.workspace_form_service.remove_action_from_form(
            workspace_id=workspace_id,
            form_id=form_id,
            action_id=action_id,
            trigger=trigger,
            user=user,
        )
        return updated_actions

    @get("/{form_id}/export-csv")
    async def export_csv_of_responses(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        responses = await self.workspace_form_service.get_responses_in_csv_format(
            workspace_id=workspace_id, form_id=str(form_id), user=user
        )
        return responses

    @patch("/{form_id}/action/{action_id}/update")
    async def update_action_from_temporal(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        action_id: PydanticObjectId,
        temporal_api_key=Depends(get_api_key),
    ):

        response = await self.workspace_form_service.update_action_from_temporal(
            workspace_id=workspace_id, form_id=form_id, action_id=action_id
        )
        return response
