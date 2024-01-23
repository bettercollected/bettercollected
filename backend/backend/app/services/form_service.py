from datetime import datetime
from http import HTTPStatus
from typing import List

from aiohttp import ServerDisconnectedError
from beanie import PydanticObjectId
from common.configs.crypto import Crypto
from common.constants import MESSAGE_FORBIDDEN
from common.models.standard_form import StandardForm, Trigger, ParameterValue, ActionState
from common.models.user import User
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from backend.app.constants.consents import default_consents
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import AddActionToFormDto, UpdateActionInFormDto, ActionUpdateType
from backend.app.models.dtos.kafka_event_dto import UserEventType
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.models.dtos.workspace_member_dto import (
    FormImporterDetails,
)
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.services.kafka_service import event_logger_service
from backend.app.services.user_tags_service import UserTagsService
from backend.app.utils import AiohttpClient
from backend.config import settings


class FormService:
    def __init__(
            self,
            workspace_user_repo: WorkspaceUserRepository,
            form_repo: FormRepository,
            workspace_form_repo: WorkspaceFormRepository,
            user_tags_service: UserTagsService,
            crypto: Crypto
    ):
        self._workspace_user_repo = workspace_user_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self.user_tags_service = user_tags_service
        self.crypto = crypto

    async def get_forms_in_workspace(
            self,
            workspace_id: PydanticObjectId,
            sort: SortRequest,
            published: bool,
            pinned_only: bool,
            user: User,
    ) -> Page[FormDtoCamelModel]:
        has_access_to_workspace = (
            await self._workspace_user_repo.has_user_access_in_workspace(
                workspace_id=workspace_id, user=user
            )
        )
        if not published and not has_access_to_workspace:
            raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)

        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id,
            not has_access_to_workspace,
            pinned_only=pinned_only,
            user=user,
            filter_closed=published or pinned_only,
        )
        if published:
            forms_query = self._form_repo.get_published_forms_in_workspace(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
                sort=sort,
            )
        else:
            forms_query = self._form_repo.get_forms_in_workspace_query(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
                is_admin=has_access_to_workspace,
                sort=sort,
            )

        forms_page = await paginate(forms_query)

        if not published:
            user_ids = [form.imported_by for form in forms_page.items]
            user_details = (
                {"users_info": []}
                if not user_ids
                else await self.fetch_user_details(user_ids=user_ids)
            )

            for form in forms_page.items:
                for user_info in user_details.get("users_info", []):
                    if form.imported_by == user_info["_id"]:
                        form.importer_details = FormImporterDetails(
                            **user_info, id=form.imported_by
                        )
                        break

        return forms_page

    async def fetch_user_details(self, user_ids):
        try:
            response = await AiohttpClient.get_aiohttp_client().get(
                f"{settings.auth_settings.BASE_URL}/users",
                params={"user_ids": user_ids},
            )
            return await response.json()
        except (ServerDisconnectedError, TimeoutError):
            raise HTTPException(
                HTTPStatus.SERVICE_UNAVAILABLE, "Could not fetch data form proxy server"
            )

    async def search_form_in_workspace(
            self, workspace_id: PydanticObjectId, query: str, published: bool, user: User
    ):
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id, is_not_admin=True, user=user
        )
        forms = await self._form_repo.search_form_in_workspace(
            workspace_id=workspace_id,
            form_ids=form_ids,
            query=query,
            published=published,
        )

        if not published:
            user_ids = [form["imported_by"] for form in forms]
            user_details = (
                {"users_info": []}
                if not user_ids
                else await self.fetch_user_details(user_ids=user_ids)
            )
            for form in forms:
                for user_info in user_details["users_info"]:
                    if form["imported_by"] == user.id:
                        form["importer_details"] = FormImporterDetails(
                            **user_info, id=form["imported_by"]
                        )
                        break
        return [FormDtoCamelModel(**form) for form in forms]

    async def get_form_by_id(
            self,
            workspace_id: PydanticObjectId,
            form_id: str,
            user: User,
            published: bool = False,
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        if not user:
            workspace_form = await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id
            )
            if not workspace_form:
                raise HTTPException(status_code=404, content="Form not found in Workspace")
            if workspace_form.settings.private or workspace_form.settings.hidden:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    content="Private Form Login to continue",
                )
        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=not is_admin,
            user=user,
            match_query={
                "$or": [{"form_id": form_id}, {"settings.custom_url": form_id}]
            },
        )
        if published:
            form = await self._form_repo.get_published_forms_in_workspace(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
            ).to_list()
        else:
            form = await self._form_repo.get_forms_in_workspace_query(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
                is_admin=is_admin,
            ).to_list()

        if not form:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
            )
        else:
            form = form[0]
        if not published:
            form = await self.add_user_details_to_form(form)
        return form

    async def add_user_details_to_form(self, form):
        user_ids = [form["imported_by"]] if form else []
        user_details = (
            {"users_info": []}
            if not user_ids
            else await self.fetch_user_details(user_ids=user_ids)
        )
        user_info = user_details.get("users_info")[0]
        form["importer_details"] = FormImporterDetails(
            **user_info, id=user_info.get("_id")
        )
        minified_form = FormDtoCamelModel(**form)
        if minified_form.consent is None:
            minified_form.consent = default_consents
        return minified_form

    async def save_form(self, form: StandardForm):
        existing_form = await FormDocument.find_one({"form_id": form.form_id})
        form_document = FormDocument(**form.dict())
        if existing_form:
            form_document.id = existing_form.id
            form_document.created_at = (
                existing_form.created_at
                if existing_form.created_at
                else datetime.utcnow()
            )
        existing_form_version = await FormVersionsDocument.find_one(
            {"form_id": form.form_id}
        )
        form_version_document = FormVersionsDocument(**form.dict(), version=1)
        if existing_form_version:
            form_version_document.id = existing_form_version.id
            form_version_document.created_at = (
                existing_form_version.created_at
                if existing_form_version.created_at
                else datetime.utcnow()
            )
        await form_version_document.save()
        return await self._form_repo.save_form(form_document)

    async def patch_settings_in_workspace_form(
            self,
            workspace_id: PydanticObjectId,
            form_id: str,
            settings: SettingsPatchDto,
            user: User,
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=form_id, is_admin=is_admin
            )
        )
        if not workspace_form:
            raise HTTPException(404, "Form not found in workspace")
        if settings.hidden is not None:
            workspace_form.settings.hidden = settings.hidden
        if settings.private is not None:
            workspace_form.settings.private = settings.private
        if settings.pinned is not None:
            workspace_form.settings.pinned = settings.pinned
        if settings.disableBranding is not None:
            workspace_form.settings.disable_branding = settings.disableBranding
        if settings.collectEmails is not None:
            workspace_form.settings.collect_emails = settings.collectEmails
        if settings.customUrl is not None:
            await self.user_tags_service.add_user_tag(
                user_id=user.id, tag=UserTagType.CUSTOM_SLUG
            )
            workspace_form_with_custom_slug = await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id, settings.customUrl
            )
            if workspace_form_with_custom_slug:
                raise HTTPException(
                    409, "Form with given custom slug already exists in the workspace!!"
                )
            workspace_form.settings.custom_url = settings.customUrl
            await event_logger_service.send_event(event_type=UserEventType.SLUG_CHANGED, user_id=user.id,
                                                  email=user.sub)
        if settings.responseDataOwnerField is not None:
            workspace_form.settings.response_data_owner_field = (
                settings.responseDataOwnerField
            )
        if settings.formCloseDate is not None:
            workspace_form.settings.form_close_date = settings.formCloseDate
        return await self._workspace_form_repo.update(workspace_form.id, workspace_form)

    async def delete_form(self, form_id: str):
        return await self._form_repo.delete_form(form_id)

    async def delete_forms(self, form_ids: List[str]):
        return await self._form_repo.delete_forms(form_ids=form_ids)

    async def create_form(self, form: StandardForm) -> FormDocument:
        return await self._form_repo.create_form(form=form)

    async def update_form(self, form_id: PydanticObjectId, form: StandardForm):
        return await self._form_repo.update_form(form_id=form_id, form=form)

    async def get_form_document_by_id(self, form_id: str):
        return await self._form_repo.get_form_document_by_id(form_id)

    async def publish_form(self, form_id: PydanticObjectId):
        form = await self._form_repo.get_form_document_by_id(str(form_id))
        latest_published_form = await self._form_repo.get_latest_version_of_form(
            form_id
        )
        if not self.has_form_been_updated(form, latest_published_form):
            return latest_published_form
        return await self._form_repo.publish_form(
            form=form,
            version=(latest_published_form.version + 1) if latest_published_form else 1,
        )

    def has_form_been_updated(
            self, form: FormDocument, latest_version: FormVersionsDocument
    ):
        if not latest_version:
            return True
        if (
                form.title == latest_version.title
                and form.description == latest_version.description
                and form.consent == latest_version.consent
                and form.fields == latest_version.fields
                and form.logo == latest_version.logo
                and form.cover_image == latest_version.cover_image
                and form.button_text == latest_version.button_text
                and form.state == latest_version.state
        ):
            return False
        return True

    async def get_form_by_version(
            self,
            workspace_id: PydanticObjectId,
            form_id: str,
            version: str | int,
            user: User,
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        if not user:
            workspace_forms = await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id
            )
            if workspace_forms.settings.private:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    content="Private Form Login to continue",
                )

        workspace_forms = (
            await self._workspace_form_repo.get_workspace_forms_in_workspace(
                workspace_id=workspace_id,
                is_not_admin=not is_admin,
                user=user,
                match_query={
                    "$or": [{"form_id": form_id}, {"settings.custom_url": form_id}]
                },
            )
        )

        if not workspace_forms:
            return HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        workspace_form = workspace_forms[0]
        if workspace_form["settings"]["provider"] != "self":
            form = await self._form_repo.get_forms_in_workspace_query(
                workspace_id=workspace_id,
                form_id_list=[form_id],
                is_admin=is_admin,
            ).to_list()

            if not form:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
                )
            return form[0]
        else:
            form = await self._form_repo.get_form_by_by_version(
                form_id=PydanticObjectId(form_id), version=version
            )
            if not form:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
                )
            form.form_id = str(form.form_id)
            return form

    async def add_action_form(self, form_id: PydanticObjectId, add_action_to_form_params: AddActionToFormDto):
        form = await self._form_repo.get_form_document_by_id(form_id=str(form_id))
        actions = []

        if form.actions is not None:

            if form.actions.get(add_action_to_form_params.trigger) is not None:
                actions.extend(form.actions.get(add_action_to_form_params.trigger))

            actions.append(ActionState(id=add_action_to_form_params.action_id, enabled=True))

            actions = actions

            form.actions[add_action_to_form_params.trigger] = actions

        else:
            form.actions = {
                add_action_to_form_params.trigger: [ActionState(id=add_action_to_form_params.action_id, enabled=True)]}
        if add_action_to_form_params.parameters:
            if form.parameters is not None:

                form.parameters[str(add_action_to_form_params.action_id)] = add_action_to_form_params.parameters
            else:
                form.parameters = {str(add_action_to_form_params.action_id): add_action_to_form_params.parameters}

        if add_action_to_form_params.secrets:
            secrets = [ParameterValue(name=secret.name, value=self.crypto.encrypt(secret.value)) for secret in
                       add_action_to_form_params.secrets]

            if form.secrets is not None:
                form.secrets[str(add_action_to_form_params.action_id)] = secrets
            else:
                form.secrets = {str(add_action_to_form_params.action_id): secrets}

        return await form.save()

    async def remove_action_from_form(self, form_id: PydanticObjectId, action_id: PydanticObjectId, trigger: Trigger):
        form = await self._form_repo.get_form_document_by_id(form_id=str(form_id))

        if form.actions and trigger in form.actions:
            form.actions[trigger] = [action for action in form.actions[trigger] if action.id != action_id]

        if form.parameters and str(action_id) in form.parameters:
            del form.parameters[str(action_id)]

        if form.secrets and str(action_id) in form.secrets:
            del form.secrets[str(action_id)]

        return (await form.save()).actions

    async def update_state_of_action_in_form(self, form_id: PydanticObjectId, update_action_dto: UpdateActionInFormDto):
        form = await self._form_repo.get_form_document_by_id(form_id=str(form_id))
        if form.actions and update_action_dto.trigger in form.actions:
            for action in form.actions[update_action_dto.trigger]:
                if action.id == update_action_dto.action_id:
                    action.enabled = True if update_action_dto.update_type == ActionUpdateType.ENABLE else False

        return await form.save()
