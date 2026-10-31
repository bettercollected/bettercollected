from datetime import datetime
from http import HTTPStatus
from typing import Any, Iterable, List, Optional

from aiohttp import ServerDisconnectedError
from common.ids import RecordId
from common.configs.crypto import Crypto
from common.constants import MESSAGE_FORBIDDEN
from common.enums.form_provider import FormProvider
from common.models.standard_form import (
    StandardForm,
    Trigger,
    ParameterValue,
    ActionState,
)
from common.models.user import User
from common.services.http_client import HttpClient
from fastapi_pagination import Page
from starlette.requests import Request

from backend.app.repositories.response_scope import response_scope
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresWorkspaceFormRepository,
)
from backend.app.constants.consents import default_consents
from backend.app.constants.themes import new_form_theme
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import (
    AddActionToFormDto,
    UpdateActionInFormDto,
    ActionUpdateType,
    ActionDto,
)
from backend.app.models.dtos.event_dto import UserEventType
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.response_dtos import FormSettingsCamelModel
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.models.dtos.workspace_member_dto import (
    FormImporterDetails,
)
from backend.app.models.enum.form_integration import FormActionType, FormIntegrationType
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.services.ai.notice_token import (
    token_for_form as ai_notice_token_for_form,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.event_service import event_logger_service
from backend.app.services.form_availability import (
    UNAVAILABLE_FULL,
    UNAVAILABLE_REASONS,
    date_unavailability,
    ensure_dates_in_order,
    is_full,
    response_limit,
)
from backend.app.services.integration_provider_factory import IntegrationProviderFactory
from backend.app.services.internal_fields import respondent_view
from backend.app.services.user_tags_service import UserTagsService
from backend.app.utils import AiohttpClient
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings


def _stub_settings(workspace_form, form) -> Optional[FormSettingsCamelModel]:
    """The settings of a private or unauthorised form's stub: the
    association's, plus the form's declared language, as the full read
    returns them."""
    language = form.settings.language if form.settings else None
    if workspace_form.settings is None:
        # as the full read: the language alone, or no settings
        return FormSettingsCamelModel(language=language) if language else None
    settings = FormSettingsCamelModel(**workspace_form.settings.model_dump())
    settings.language = language
    # the limit is the creator's: respondents learn only that a form is full
    settings.response_limit = None
    return settings


def _unavailable_stub(form: Any, reason: str, settings: Any = None) -> dict:
    """What a respondent gets of a form that takes no responses (closed, not
    open yet, or full), on every read that would serve its questions: the
    welcome page and its look, with ``unavailable`` naming the reason and no
    questions (services/form_availability.py). ``form`` is a stored dict or a
    document; ``settings`` the association's (default: the form's folded
    ones). The stub never carries the response limit."""

    def get(key):
        if isinstance(form, dict):
            return form.get(key)
        return getattr(form, key, None)

    form_id = get("form_id")
    shown = settings if settings is not None else get("settings")
    if isinstance(shown, dict):
        shown = {**shown, "response_limit": None}
    elif shown is not None:
        shown = shown.model_copy(update={"response_limit": None})
    return {
        "formId": str(form_id) if form_id is not None else None,
        "builderVersion": get("builder_version"),
        "title": get("title"),
        "description": get("description"),
        "coverImage": get("cover_image"),
        "logo": get("logo"),
        "logoPosition": get("logo_position"),
        "logoAlt": get("logo_alt"),
        "useWorkspaceLogo": get("use_workspace_logo"),
        "welcomePage": get("welcome_page"),
        "theme": get("theme"),
        "settings": shown,
        "unavailable": reason,
    }


def _is_unavailable_stub(form: Any) -> bool:
    return isinstance(form, dict) and form.get("unavailable") in UNAVAILABLE_REASONS


def _declared_language(form) -> Optional[str]:
    """The language a form or a published version declares (its own
    ``settings.language``): a change to it alone is worth a new version."""
    return form.settings.language if form.settings else None


class FormService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        form_repo: PostgresFormRepository,
        workspace_form_repo: PostgresWorkspaceFormRepository,
        user_tags_service: UserTagsService,
        crypto: Crypto,
        http_client: HttpClient,
        integration_provider: IntegrationProviderFactory,
        form_response_repo=None,
    ):
        # the responses repository: counts for a form's response limit
        self._form_response_repo = form_response_repo
        self._authorization = authorization_service
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self.user_tags_service = user_tags_service
        self.crypto: Crypto = crypto
        self.http_client = http_client
        self.integration_provider = integration_provider

    async def get_forms_in_workspace(
        self,
        workspace_id: RecordId,
        sort: SortRequest,
        published: bool,
        pinned_only: bool,
        user: User,
    ) -> Page[FormDtoCamelModel]:
        has_access_to_workspace = await self._staff_view(user, workspace_id, published)

        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id,
            not has_access_to_workspace,
            pinned_only=pinned_only,
            user=user,
            filter_closed=published or pinned_only,
        )
        if published or pinned_only:
            workspace_form_ids = await self._without_full_forms(
                workspace_id, workspace_form_ids
            )
        if published:
            forms_page = await self._form_repo.paginate_published_forms_in_workspace(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
                sort=sort,
            )
        else:
            forms_page = await self._form_repo.paginate_forms_in_workspace(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
                is_admin=has_access_to_workspace,
                sort=sort,
            )

        if not has_access_to_workspace:
            # Public listing: internal fields belong to the organisation.
            for form in forms_page.items:
                respondent_view(form)

        if has_access_to_workspace and not published:
            importers = await self._importer_details(
                form.imported_by for form in forms_page.items
            )
            for form in forms_page.items:
                user_info = importers.get(form.imported_by)
                if user_info is not None:
                    form.importer_details = FormImporterDetails(
                        **user_info, id=form.imported_by
                    )

        return forms_page

    async def _staff_view(
        self, user: Optional[User], workspace_id: RecordId, published: bool
    ) -> bool:
        """Whether ``user`` sees the workspace's forms as staff (``form.read``).
        Members get the dashboard listing, search and single-form reads;
        everyone else only the published forms: drafts (``published`` false)
        are 403 for them. Staff
        alone get importer details (members' names and emails)."""
        staff = await self._authorization.has_permission(
            user, Permission.FORM_READ, workspace_id
        )
        if not published and not staff:
            raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)
        return staff

    async def _importer_details(self, importer_ids: Iterable[Optional[str]]):
        """importer id -> the auth service's details for them: one call with
        each importer once, however many of their forms are on the page."""
        unique_ids = list(dict.fromkeys(i for i in importer_ids if i))
        if not unique_ids:
            return {}
        user_details = await self.fetch_user_details(user_ids=unique_ids)
        return {
            user_info["_id"]: user_info
            for user_info in user_details.get("users_info") or []
            if user_info.get("_id")
        }

    async def fetch_user_details(self, user_ids):
        try:
            response = await AiohttpClient.get_aiohttp_client().get(
                f"{settings.auth_settings.BASE_URL}/users",
                params={"user_ids": user_ids},
                headers=auth_service_headers(),
            )
            return await response.json()
        except (ServerDisconnectedError, TimeoutError):
            raise HTTPException(
                HTTPStatus.SERVICE_UNAVAILABLE, "Could not fetch data form proxy server"
            )

    async def search_form_in_workspace(
        self, workspace_id: RecordId, query: str, published: bool, user: User
    ):
        # before any query: drafts are staff-only, as in the listing
        staff = await self._staff_view(user, workspace_id, published)
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=True,
            user=user,
            # as the public listing: closed, not yet open and full forms are not
            # offered to respondents
            filter_closed=not staff,
        )
        if not staff:
            form_ids = await self._without_full_forms(workspace_id, form_ids)
        forms = await self._form_repo.search_form_in_workspace(
            workspace_id=workspace_id,
            form_ids=form_ids,
            query=query,
            published=published,
        )
        if not staff:
            for form in forms:
                respondent_view(form)

        if staff and not published:
            importers = await self._importer_details(
                form.get("imported_by") for form in forms
            )
            for form in forms:
                user_info = importers.get(form.get("imported_by"))
                if user_info is not None:
                    form["importer_details"] = FormImporterDetails(
                        **user_info, id=form["imported_by"]
                    )
        return [FormDtoCamelModel(**form) for form in forms]

    async def get_form_by_id(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User,
        published: bool = False,
        draft: bool = False,
    ):
        # Members see the form as staff; respondents and the public don't.
        # Drafts are staff-only, as in the listing and search: 403 before any
        # lookup, whether or not the form exists. ``draft`` (the draft of a
        # never-published form in place of its published version) likewise.
        is_admin = await self._staff_view(user, workspace_id, published)
        form = await self._get_form_by_id(
            workspace_id=workspace_id,
            form_id=form_id,
            user=user,
            is_admin=is_admin,
            published=published,
            draft=draft and is_admin,
        )
        if is_admin:
            return form
        # The questions of a form that takes no responses (closed, not open
        # yet, full) are not served to respondents: its welcome page says why.
        # Who may see the form at all is decided first: the stubs of private
        # and hidden forms (camelCase keys, no questions) are served as they
        # are.
        if published and isinstance(form, dict) and "form_id" in form:
            reason = await self._unavailable_reason(
                workspace_id, form["form_id"], form.get("settings")
            )
            if reason:
                return _unavailable_stub(form, reason)
        # Respondents and the public never receive internal fields.
        return respondent_view(form)

    async def _response_count(self, workspace_id: RecordId, form_id: str) -> int:
        """The responses stored for the form in this workspace (what the
        response limit counts)."""
        scope = await response_scope(
            self._workspace_form_repo, workspace_id, [str(form_id)]
        )
        return await self._form_response_repo.count_responses_for_form_ids(scope)

    async def _unavailable_reason(
        self, workspace_id: RecordId, form_id: str, settings: Any
    ) -> Optional[str]:
        """Why a respondent gets this form's welcome page without its
        questions: ``closed``, ``not_yet_open`` or ``full``, else None. The
        count is read only for a form that has a limit."""
        reason = date_unavailability(settings)
        if reason or response_limit(settings) is None:
            return reason
        if is_full(settings, await self._response_count(workspace_id, form_id)):
            return UNAVAILABLE_FULL
        return None

    async def _without_full_forms(
        self, workspace_id: RecordId, form_ids: List[str]
    ) -> List[str]:
        """``form_ids`` without the forms that have used up their response
        limit (one count query for all the limited forms of the list)."""
        limits = await self._workspace_form_repo.get_response_limits(
            workspace_id, form_ids
        )
        if not limits:
            return form_ids
        scope = await response_scope(self._workspace_form_repo, workspace_id, limits)
        counts = await self._form_response_repo.count_responses_by_form_ids(scope)
        return [
            form_id
            for form_id in form_ids
            if form_id not in limits or counts.get(form_id, 0) < limits[form_id]
        ]

    async def ai_notice_token(
        self, workspace_id: RecordId, form_id_or_slug: str
    ) -> Optional[str]:
        """The AI notice token for a respondent's page of this form (#752), or
        None while the form shows no AI notice."""
        association = (
            await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id_or_slug
            )
        )
        return ai_notice_token_for_form(workspace_id, association)

    async def _get_form_by_id(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User,
        is_admin: bool,
        published: bool = False,
        draft: bool = False,
    ):
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id
            )
        )
        if not user:
            if not workspace_form:
                raise HTTPException(
                    status_code=404, content="Form not found in Workspace"
                )
            if (
                workspace_form.settings.private or workspace_form.settings.hidden
            ) and published:
                form = await self._form_repo.get_latest_version_of_form(
                    form_id=RecordId(workspace_form.form_id)
                )
                return {
                    "formId": form.form_id,
                    "builderVersion": form.builder_version,
                    "welcomePage": form.welcome_page,
                    "theme": form.theme,
                    "settings": _stub_settings(workspace_form, form),
                }
        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=not is_admin,
            user=user,
            form_id_or_slug=form_id,
        )
        if published:
            authorized_form = await self._form_repo.get_published_forms_in_workspace(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
                get_actions=is_admin,
            )
            if not authorized_form:
                if draft:
                    form = await self._form_repo.get_forms_in_workspace(
                        workspace_id=workspace_id,
                        form_id_list=workspace_form_ids,
                        is_admin=is_admin,
                    )
                    if not form:
                        raise HTTPException(
                            status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
                        )
                    form = form[0]
                    form = await self.add_user_details_to_form(form, is_admin)
                    return form
                if not workspace_form:
                    raise HTTPException(
                        status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
                    )
                form = await self._form_repo.get_latest_version_of_form(
                    form_id=RecordId(workspace_form.form_id)
                )
                if not form:
                    raise HTTPException(
                        status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
                    )
                else:
                    return {
                        "formId": form.form_id,
                        "builderVersion": form.builder_version,
                        "welcomePage": form.welcome_page,
                        "theme": form.theme,
                        "settings": _stub_settings(workspace_form, form),
                        "unauthorized": True,
                    }
            else:
                return authorized_form[0]

        else:
            form = await self._form_repo.get_forms_in_workspace(
                workspace_id=workspace_id,
                form_id_list=workspace_form_ids,
                is_admin=is_admin,
            )
        if not form:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
            )
        else:
            form = form[0]
        form = await self.add_user_details_to_form(form, is_admin)
        return form

    async def add_user_details_to_form(self, form, staff: bool):
        """The form as a DTO; ``staff`` (``form.read``) also get its
        importer's details, the members' names and emails being theirs only."""
        if staff:
            importers = await self._importer_details([form.get("imported_by")])
            user_info = importers.get(form.get("imported_by"))
            if user_info is not None:
                form["importer_details"] = FormImporterDetails(
                    **user_info, id=form["imported_by"]
                )
        minified_form = FormDtoCamelModel(**form)
        if minified_form.consent is None:
            minified_form.consent = default_consents
        return minified_form

    async def save_form(self, form: StandardForm):
        """Persist an imported form as version 1. Re-importing a form replaces
        its document and its version 1 rather than adding duplicates: form_id
        is unique in the forms store (and Mongo readers use find_one on it)."""
        form_document = FormDocument(**form.model_dump(mode="json"))
        existing = await self._form_repo.get_form_document_by_id(form_document.form_id)
        if existing:
            form_document.id = existing.id
            form_document.created_at = existing.created_at
        if form_document.theme is None:
            # The provider sent no colours of its own: a first import starts
            # with the new-form theme, a re-import keeps the stored one.
            form_document.theme = existing.theme if existing else new_form_theme()
        form_version_document = FormVersionsDocument(
            **form.model_dump(mode="json"), version=1
        )
        form_version_document.theme = form_document.theme
        existing_version = await self._form_repo.get_form_by_by_version(
            form_document.form_id, 1
        )
        if existing_version:
            form_version_document.id = existing_version.id
            form_version_document.created_at = existing_version.created_at
        await self._form_repo.save_form_version(form_version_document)
        return await self._form_repo.save_form(form_document)

    async def check_form_in_workspace(self, workspace_id: RecordId, form_id):
        if not await self._workspace_form_repo.find_workspace_form(
            workspace_id, str(form_id)
        ):
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in workspace")

    async def patch_settings_in_workspace_form(
        self,
        workspace_id: RecordId,
        form_id: str,
        settings: SettingsPatchDto,
        user: User,
    ):
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        if settings.hidden is not None or settings.private is not None:
            # who may see and answer the form
            await self._authorization.authorize(
                user, Permission.FORM_SHARE, workspace_id
            )
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=form_id, is_admin=True
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
        if settings.disable_branding is not None:
            workspace_form.settings.disable_branding = settings.disable_branding
        if settings.require_verified_identity is not None:
            workspace_form.settings.require_verified_identity = (
                settings.require_verified_identity
            )
        if settings.show_submission_number is not None:
            workspace_form.settings.show_submission_number = (
                settings.show_submission_number
            )
        if settings.allow_editing_response is not None:
            workspace_form.settings.allow_editing_response = (
                settings.allow_editing_response
            )

        if settings.allow_save_draft is not None:
            workspace_form.settings.allow_save_draft = settings.allow_save_draft
        if settings.draft_retention_days is not None:
            # 0 goes back to the default
            workspace_form.settings.draft_retention_days = (
                settings.draft_retention_days or None
            )

        if settings.show_original_form is not None:
            workspace_form.settings.show_original_form = settings.show_original_form

        # Respondent feedback: only on forms collected here — an imported
        # form's responses are re-imported from the provider. Switching it or
        # its statuses is a form setting (form.edit); posting is
        # response.annotate.
        if settings.respondent_feedback_enabled:
            if workspace_form.settings.provider != "self":
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    "Responding to submissions is only available for forms "
                    "built in BetterCollected.",
                )
        if settings.respondent_feedback_enabled is not None:
            workspace_form.settings.respondent_feedback_enabled = (
                settings.respondent_feedback_enabled
            )
        if settings.feedback_statuses is not None:
            workspace_form.settings.feedback_statuses = settings.feedback_statuses

        # Trust-layer content — empty string clears a value.
        if settings.privacy_policy_url is not None:
            workspace_form.settings.privacy_policy_url = (
                settings.privacy_policy_url or None
            )
        if settings.purpose is not None:
            workspace_form.settings.purpose = settings.purpose or None
        if settings.retention_text is not None:
            workspace_form.settings.retention_text = settings.retention_text or None
        if settings.response_expiration_type is not None:
            # Applies to submissions from now on (services/retention.py).
            workspace_form.settings.response_expiration_type = (
                settings.response_expiration_type
            )
            workspace_form.settings.response_expiration = settings.response_expiration

        if settings.custom_url is not None:
            await self.user_tags_service.add_user_tag(
                user_id=user.id, tag=UserTagType.CUSTOM_SLUG
            )
            workspace_form_with_custom_slug = await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id, settings.custom_url
            )
            if workspace_form_with_custom_slug:
                raise HTTPException(
                    409, "Form with given custom slug already exists in the workspace!!"
                )
            workspace_form.settings.custom_url = settings.custom_url
            await event_logger_service.send_event(
                event_type=UserEventType.SLUG_CHANGED, user_id=user.id
            )
        if settings.response_data_owner_field is not None:
            workspace_form.settings.response_data_owner_field = (
                settings.response_data_owner_field
            )
        if settings.form_close_date is not None or settings.form_open_date is not None:
            # the open date stays before the close date, whichever of the two
            # is sent (the stored one counts for the one that is not)
            new_open = (
                settings.form_open_date
                if settings.form_open_date is not None
                else workspace_form.settings.form_open_date
            )
            new_close = (
                settings.form_close_date
                if settings.form_close_date is not None
                else workspace_form.settings.form_close_date
            )
            try:
                ensure_dates_in_order(new_open, new_close)
            except ValueError as error:
                raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, str(error))
            if settings.form_close_date is not None:
                workspace_form.settings.form_close_date = settings.form_close_date
            if settings.form_open_date is not None:
                workspace_form.settings.form_open_date = settings.form_open_date
        if settings.response_limit is not None:
            # 0 removes the limit
            workspace_form.settings.response_limit = settings.response_limit or None
        return await self._workspace_form_repo.update(workspace_form.id, workspace_form)

    async def delete_form(self, form_id: str):
        return await self._form_repo.delete_form(form_id)

    async def delete_forms(self, form_ids: List[str]):
        return await self._form_repo.delete_forms(form_ids=form_ids)

    async def create_form(self, form: StandardForm) -> FormDocument:
        return await self._form_repo.create_form(form=form)

    async def update_form(self, form_id: RecordId, form: StandardForm):
        return await self._form_repo.update_form(form_id=form_id, form=form)

    async def update_form_if_unchanged(
        self,
        form_id: RecordId,
        form: StandardForm,
        expected_updated_at: datetime,
    ):
        """``update_form`` only while the stored draft is not newer than
        ``expected_updated_at``; otherwise 409 (form_concurrency.py)."""
        return await self._form_repo.update_form_if_unchanged(
            form_id=form_id, form=form, expected_updated_at=expected_updated_at
        )

    async def get_form_document_by_id(self, form_id: str):
        return await self._form_repo.get_form_document_by_id(form_id)

    async def publish_form(self, form_id: RecordId):
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
            and form.hidden_fields == latest_version.hidden_fields
            and form.logo == latest_version.logo
            and form.logo_position == latest_version.logo_position
            and form.logo_alt == latest_version.logo_alt
            and form.use_workspace_logo == latest_version.use_workspace_logo
            and form.cover_image == latest_version.cover_image
            and form.button_text == latest_version.button_text
            and form.state == latest_version.state
            and form.welcome_page == latest_version.welcome_page
            and form.thankyou_page == latest_version.thankyou_page
            and form.theme == latest_version.theme
            and _declared_language(form) == _declared_language(latest_version)
        ):
            return False
        return True

    async def get_form_by_version(
        self,
        workspace_id: RecordId,
        form_id: str,
        version: str | int,
        user: User,
    ):
        # Members see the form as staff; respondents and the public don't.
        is_admin = await self._authorization.has_permission(
            user, Permission.FORM_READ, workspace_id
        )
        form = await self._get_form_by_version(
            workspace_id, form_id, version, user, is_admin
        )
        if is_admin or isinstance(form, HTTPException) or _is_unavailable_stub(form):
            return form
        return respondent_view(form)

    async def _get_form_by_version(
        self,
        workspace_id: RecordId,
        form_id: str,
        version: str | int,
        user: User,
        is_admin: bool,
    ):
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
                form_id_or_slug=form_id,
            )
        )

        if not workspace_forms:
            return HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        workspace_form = workspace_forms[0]
        # The questions of a form that takes no responses reach staff only, on
        # this read as on the published one (services/form_availability.py).
        unavailable = (
            await self._unavailable_reason(
                workspace_id, workspace_form["form_id"], workspace_form.get("settings")
            )
            if not is_admin
            else None
        )
        closed_settings = workspace_form.get("settings")
        if workspace_form["settings"]["provider"] != "self":
            form = await self._form_repo.get_forms_in_workspace(
                workspace_id=workspace_id,
                form_id_list=[form_id],
                is_admin=is_admin,
            )

            if not form:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
                )
            if unavailable:
                return _unavailable_stub(form[0], unavailable, closed_settings)
            return form[0]
        else:
            form = await self._form_repo.get_form_by_by_version(
                form_id=RecordId(form_id), version=version
            )
            if not form:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
                )
            form.form_id = str(form.form_id)
            if unavailable:
                return _unavailable_stub(form, unavailable, closed_settings)
            return form

    async def add_action_form(
        self,
        form_id: RecordId,
        add_action_to_form_params: AddActionToFormDto,
        action: ActionDto,
    ):
        form = await self._form_repo.get_form_document_by_id(form_id=str(form_id))
        actions = []

        if form.actions is not None:

            if form.actions.get(add_action_to_form_params.trigger) is not None:
                actions.extend(form.actions.get(add_action_to_form_params.trigger))

            actions.append(
                ActionState(id=add_action_to_form_params.action_id, enabled=True)
            )

            actions = actions

            form.actions[add_action_to_form_params.trigger] = actions

        else:
            form.actions = {
                add_action_to_form_params.trigger: [
                    ActionState(id=add_action_to_form_params.action_id, enabled=True)
                ]
            }
        if add_action_to_form_params.parameters:
            if form.parameters is not None:
                form.parameters[str(add_action_to_form_params.action_id)] = (
                    add_action_to_form_params.parameters
                )
            else:
                form.parameters = {
                    str(
                        add_action_to_form_params.action_id
                    ): add_action_to_form_params.parameters
                }
            if action.type == FormActionType.EXTERNAL:
                form_params = await self.handle_external_integrations_services(
                    action_params=add_action_to_form_params,
                    integration_name=FormIntegrationType(action.name),
                    form_id=form_id,
                )
                form.parameters[str(add_action_to_form_params.action_id)].append(
                    form_params
                )

        if add_action_to_form_params.secrets:
            secrets = [
                ParameterValue(
                    name=secret.name, value=self.crypto.encrypt(secret.value)
                )
                for secret in add_action_to_form_params.secrets
            ]

            if form.secrets is not None:
                form.secrets[str(add_action_to_form_params.action_id)] = secrets
            else:
                form.secrets = {str(add_action_to_form_params.action_id): secrets}

        return await self._form_repo.save_form(form)

    async def remove_action_from_form(
        self, form_id: RecordId, action_id: RecordId, trigger: Trigger
    ):
        form = await self._form_repo.get_form_document_by_id(form_id=str(form_id))

        if form.actions and trigger in form.actions:
            form.actions[trigger] = [
                action for action in form.actions[trigger] if action.id != action_id
            ]

        if form.parameters and str(action_id) in form.parameters:
            del form.parameters[str(action_id)]

        if form.secrets and str(action_id) in form.secrets:
            del form.secrets[str(action_id)]

        return (await self._form_repo.save_form(form)).actions

    async def update_state_of_action_in_form(
        self, form_id: RecordId, update_action_dto: UpdateActionInFormDto
    ):
        form = await self._form_repo.get_form_document_by_id(form_id=str(form_id))
        if form.actions and update_action_dto.trigger in form.actions:
            for action in form.actions[update_action_dto.trigger]:
                if action.id == update_action_dto.action_id:
                    action.enabled = (
                        True
                        if update_action_dto.update_type == ActionUpdateType.ENABLE
                        else False
                    )

        return await self._form_repo.save_form(form)

    async def handle_external_integrations_services(
        self,
        action_params: AddActionToFormDto,
        integration_name: FormIntegrationType,
        form_id: RecordId,
    ):
        form_params = await self.integration_provider.get_integration_provider(
            integration_type=integration_name
        ).add_google_sheet_id_to_form_action(
            action_params=action_params, form_id=str(form_id)
        )
        return form_params

    async def get_latest_version_of_form(self, form_id: RecordId):
        return await self._form_repo.get_latest_version_of_form(form_id)
