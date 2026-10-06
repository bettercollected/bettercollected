import datetime as dt
import json
import re
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Sequence, Set

from beanie import PydanticObjectId
from common.constants import MESSAGE_NOT_FOUND
from common.models.standard_form import (
    InternalAnswerMeta,
    StandardFormResponse,
    StandardFormResponseAnswer,
    StandardFormField,
    StandardFormFieldType,
)
from common.models.user import User
from common.services.crypto_service import crypto_service
from fastapi_pagination import Page

from backend.app.constants.consents import default_consent_responses
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.form_response_dto import (
    InternalAnswersResponse,
    SingleSubmissionResponse,
)
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.respondent_feedback_dto import StaffFeedback
from backend.app.models.dtos.response_dtos import (
    StandardFormCamelModel,
    StandardFormFieldCamelModel,
    StandardFormResponseCamelModel,
)
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.enum.permission import Permission
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.internal_fields import (
    fields_by_id,
    internal_field_ids,
    internal_fields,
    strip_internal_answers,
    respondent_view,
    validate_internal_answer,
)
from backend.app.services.respondent_feedback import (
    current_status,
    decrypt_feedback,
    emails_respondent,
    feedback_entries,
    present_to_respondent,
    staff_feedback,
)
from backend.app.utils.hash import hash_string

# An uploaded answer file's id is client-supplied: only a plain id (no "/",
# not "." or "..") may ever become part of a storage key, so it can't name
# another workspace's object.
_PLAIN_FILE_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


def is_plain_file_id(value) -> bool:
    return (
        isinstance(value, str)
        and _PLAIN_FILE_ID.fullmatch(value) is not None
        and value not in (".", "..")
    )


class FormResponseService:
    def __init__(
        self,
        form_response_repo: FormResponseRepository,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
        authorization_service: AuthorizationService,
        aws_service: AWSS3Service,
        workspace_repo: WorkspaceRepository,
    ):
        self._form_response_repo = form_response_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self._authorization = authorization_service
        self._aws_service = aws_service
        self._workspace_repo = workspace_repo

    async def get_all_workspace_responses(
        self,
        workspace_id: PydanticObjectId,
        filter_query: FormResponseFilterQuery,
        sort: SortRequest,
        request_for_deletion: bool,
        user: User,
        data_subjects: bool = None,
    ):
        # Deletion requests and the data subjects (responders) are the privacy
        # programme; the answers themselves are response.read.
        await self._authorization.authorize(
            user,
            (
                Permission.PRIVACY_MANAGE
                if data_subjects or request_for_deletion
                else Permission.RESPONSE_READ
            ),
            workspace_id,
        )
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id
        )
        responses_page = await self._form_response_repo.list(
            form_ids,
            request_for_deletion,
            data_subjects=data_subjects,
            filter_query=filter_query,
            sort=sort,
        )
        if not (data_subjects or request_for_deletion):
            return self.decrypt_response_page(
                workspace_id=workspace_id, responses_page=responses_page
            )
        return responses_page

    async def get_user_submissions(
        self,
        workspace_id: PydanticObjectId,
        user: User,
        request_for_deletion: bool = False,
    ):
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id
        )
        user_responses = await self._form_response_repo.get_user_submissions(
            form_ids=form_ids, user=user, request_for_deletion=request_for_deletion
        )
        # A respondent's own listing never carries staff-entered values; of
        # the feedback only the current status (no staff identity).
        for item in user_responses.items:
            strip_internal_answers(item)
            if not request_for_deletion:
                present_to_respondent(item, None, enabled=False, with_entries=False)
        if not request_for_deletion:
            return self.decrypt_response_page(
                workspace_id=workspace_id, responses_page=user_responses
            )
        return user_responses

    async def get_workspace_form_submissions(
        self,
        workspace_id: PydanticObjectId,
        request_for_deletion: bool,
        form_id: str,
        filter_query: FormResponseFilterQuery,
        sort: SortRequest,
        user: User,
    ):
        await self._authorization.authorize(
            user,
            (
                Permission.PRIVACY_MANAGE
                if request_for_deletion
                else Permission.RESPONSE_READ
            ),
            workspace_id,
        )
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id, form_id
            )
        )
        if not workspace_form:
            raise HTTPException(
                HTTPStatus.NOT_FOUND, "Form not found in the workspace."
            )
        form_responses = await self._form_response_repo.list(
            [form_id], request_for_deletion, filter_query, sort
        )
        form = await self._form_repo.get_form_document_by_id(form_id)
        file_fields = []
        if form is not None:
            file_fields = get_fields_of_type_file_upload(form)

        if not request_for_deletion:
            response_page = self.decrypt_response_page(
                workspace_id=workspace_id,
                responses_page=form_responses,
            )
            for response in response_page.items:
                if file_fields:
                    response = self.generate_presigned_url_for_each_response(
                        file_fields, response, workspace_id
                    )
            return response_page
        return form_responses

    async def check_member_and_form_in_workspace(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        """Aggregate flow analytics: 403 without analytics.read, 404 unless
        the form belongs to the workspace."""
        await self._authorization.authorize(
            user, Permission.ANALYTICS_READ, workspace_id, form_id=form_id
        )

    async def get_workspace_form_all_submissions(
        self,
        form_id: str,
        workspace_id: PydanticObjectId,
        user: User,
        permission: Permission = Permission.RESPONSE_READ,
    ):
        # Every response of the form, unpaginated. The flow view's
        # per-response insights read it with response.read; the CSV download
        # goes through the export route, which asks for response.export.
        await self._authorization.authorize(user, permission, workspace_id)
        # Scope the form to the workspace as well: without this the caller could
        # name any workspace they belong to and read another workspace's form.
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id, form_id
            )
        )
        if not workspace_form:
            raise HTTPException(
                HTTPStatus.NOT_FOUND, "Form not found in the workspace."
            )
        form_responses = await self._form_response_repo.list_by_form_id(form_id)
        return self.decrypt_form_responses(
            workspace_id=workspace_id, responses=form_responses
        )

    async def get_workspace_submission(
        self, workspace_id: PydanticObjectId, response_id: str, user: User
    ):
        # Staff read any response of the workspace; otherwise this is the
        # respondent's own submission (checked by identity below).
        is_admin = await self._authorization.has_permission(
            user, Permission.RESPONSE_READ, workspace_id
        )
        response = await self._form_response_repo.get_response(response_id)
        if not response:
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        if response.form_version:
            form = await self._form_repo.get_form_by_by_version(
                response.form_id, response.form_version if response.form_version else 1
            )
        else:
            form = await self._form_repo.get_latest_version_of_form(response.form_id)
            form = await self._form_repo.get_form_document_by_id(response.form_id)
        if not form:
            form = await self._form_repo.get_form_document_by_id(response.form_id)
        deletion_request = (
            await self._form_response_repo.find_deletion_request_by_response_id(
                response_id
            )
        )
        workspace_form = await self._workspace_form_repo.find_workspace_form(
            workspace_id, form.form_id
        )
        if not workspace_form:
            raise HTTPException(404, "Form not found in this workspace")

        if not (
            is_admin
            or response.dataOwnerIdentifier == user.sub
            or response.anonymous_identity == hash_string(user.sub)
        ):
            raise HTTPException(403, "You are not authorized to perform this action.")

        response = StandardFormResponseCamelModel(**response.model_dump())
        if not is_admin:
            # The respondent's "view my submission": no internal values.
            strip_internal_answers(response)
        if response.consent is None:
            response.consent = default_consent_responses
        if deletion_request is not None:
            response.deletion_status = deletion_request.status
        form = FormDtoCamelModel(**form.model_dump())
        form.settings = workspace_form.settings
        staff_internal_fields = None
        if is_admin:
            staff_internal_fields = [
                StandardFormFieldCamelModel(**field.model_dump())
                for field in await self.internal_field_definitions(response.form_id)
            ]
        else:
            respondent_view(form)
        response.form_title = form.title
        decrypted_response = self.decrypt_form_response(
            workspace_id=workspace_id, response=response
        )
        staff_view = None
        if is_admin:
            entries = feedback_entries(decrypted_response)  # decrypted above
            staff_view = StaffFeedback(
                entries=staff_feedback(entries),
                current_status=current_status(entries),
                can_post=bool(workspace_form.settings.respondent_feedback_enabled)
                and await self._authorization.has_permission(
                    user, Permission.RESPONSE_ANNOTATE, workspace_id
                ),
                notifies_respondent=emails_respondent(
                    workspace_form.settings, response
                ),
            )
        else:
            present_to_respondent(
                decrypted_response,
                await self._workspace_title(workspace_id),
                enabled=bool(workspace_form.settings.respondent_feedback_enabled),
            )
        for key, decrypted_answer in decrypted_response.answers.items():
            decrypted_answer = (
                decrypted_answer.model_dump(mode="json")
                if isinstance(decrypted_answer, StandardFormResponseAnswer)
                else decrypted_answer
            )
            if decrypted_answer.get("file_metadata") is not None:
                decrypted_response.answers[key]["file_metadata"]["url"] = (
                    self.file_download_url(
                        workspace_id,
                        response.form_id,
                        response.response_id,
                        decrypted_answer["file_metadata"].get("id"),
                    )
                )

        return SingleSubmissionResponse(
            form=form,
            response=decrypted_response,
            internal_fields=staff_internal_fields,
            feedback=staff_view,
        )

    async def _workspace_title(self, workspace_id: PydanticObjectId) -> Optional[str]:
        """The organisation's name, shown to respondents as the author of
        feedback in place of the staff member who posted it."""
        workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
        # not the handle: a default workspace is named after its owner's id
        return (workspace.title or None) if workspace else None

    async def request_for_response_deletion(
        self, workspace_id: PydanticObjectId, response_id: str, user: User
    ):
        # Staff may file one for any response; otherwise only its respondent.
        is_admin = await self._authorization.has_permission(
            user, Permission.PRIVACY_MANAGE, workspace_id
        )
        # TODO : Handle case for multiple form import by other user
        response = await self._form_response_repo.get_response(response_id)
        # Membership only counts for responses to this workspace's forms.
        if not response or not await self._workspace_form_repo.find_workspace_form(
            workspace_id, response.form_id
        ):
            raise HTTPException(HTTPStatus.NOT_FOUND, "Response not found in workspace")

        # Anonymous responses carry no dataOwnerIdentifier — their owner is
        # recognisable only by the anonymous identity hash. Without this check
        # the people the product promised anonymity to were the only ones who
        # couldn't exercise their deletion right (403).
        if not (
            is_admin
            or response.dataOwnerIdentifier == user.sub
            or (
                response.anonymous_identity is not None
                and response.anonymous_identity == hash_string(user.sub)
            )
        ):
            raise HTTPException(403, "You are not authorized to perform this action.")

        deletion_request = (
            await self._form_response_repo.find_deletion_request_by_response_id(
                response_id
            )
        )
        if deletion_request:
            raise HTTPException(
                400,
                "Error: Deletion request already exists for the response : "
                + response_id,
            )

        await self._form_response_repo.add_deletion_request(response, response_id)

    async def get_responses_count_in_workspace(self, workspace_form_ids: List[str]):
        return await self._form_response_repo.count_responses_for_form_ids(
            workspace_form_ids
        )

    async def get_deletion_requests_count_in_workspace(self, form_ids: List[str]):
        return await self._form_response_repo.get_deletion_requests_count_in_workspace(
            form_ids
        )

    async def delete_form_responses(self, form_id):
        return await self._form_response_repo.delete_by_form_id(form_id)

    async def delete_deletion_requests(self, form_id):
        return await self._form_response_repo.delete_deletion_requests(form_id=form_id)

    async def delete_form_responses_of_form_ids(self, form_ids):
        return await self._form_response_repo.delete_by_form_ids(form_ids=form_ids)

    async def delete_deletion_requests_of_form_ids(self, form_ids):
        return await self._form_response_repo.delete_deletion_requests_by_form_ids(
            form_ids=form_ids
        )

    def decrypt_response_page(
        self,
        workspace_id: PydanticObjectId,
        responses_page: Page[StandardFormResponseCamelModel],
    ):
        responses_page.items = self.decrypt_form_responses(
            workspace_id=workspace_id,
            responses=responses_page.items,
        )
        return responses_page

    async def get_all_expiring_forms_responses(self):
        return await self._form_response_repo.get_all_expiring_responses()

    async def get_response_by_id(self, response_id: str):
        return await self._form_response_repo.get_response(response_id=response_id)

    def decrypt_form_responses(
        self,
        workspace_id: PydanticObjectId,
        responses: Sequence[StandardFormResponseCamelModel],
    ):
        for response in responses:
            response = self.decrypt_form_response(
                workspace_id=workspace_id, response=response
            )
        return responses

    def decrypt_form_response(
        self,
        workspace_id: PydanticObjectId,
        response: StandardFormResponseCamelModel,
    ):
        if not isinstance(response.answers, dict):
            response.answers = json.loads(
                crypto_service.decrypt(
                    workspace_id=workspace_id,
                    form_id=response.form_id,
                    data=response.answers,
                )
            )
        if isinstance(response.hidden_fields, (bytes, str)):
            response.hidden_fields = json.loads(
                crypto_service.decrypt(
                    workspace_id=workspace_id,
                    form_id=response.form_id,
                    data=response.hidden_fields,
                )
            )
        if isinstance(getattr(response, "internal_answers", None), (bytes, str)):
            response.internal_answers = json.loads(
                crypto_service.decrypt(
                    workspace_id=workspace_id,
                    form_id=response.form_id,
                    data=response.internal_answers,
                )
            )
        if getattr(response, "respondent_feedback", None):
            response.respondent_feedback = decrypt_feedback(
                workspace_id, response.form_id, response.respondent_feedback
            )
        return response

    async def submit_form_response(
        self,
        form_id: PydanticObjectId,
        response: StandardFormResponse,
        workspace_id: PydanticObjectId,
    ):
        response = await self._form_response_repo.save_form_response(
            form_id=form_id, response=response, workspace_id=workspace_id
        )

        return self.decrypt_form_response(workspace_id=workspace_id, response=response)

    async def patch_form_response(
        self,
        form_id: PydanticObjectId,
        response_id: PydanticObjectId,
        response: StandardFormResponse,
        workspace_id: PydanticObjectId,
        user=User,
    ):
        updated_response = await self._form_response_repo.patch_form_response(
            form_id=form_id,
            response_id=response_id,
            response=response,
            workspace_id=workspace_id,
            user=user,
        )
        return updated_response

    async def delete_form_response(
        self,
        form_id: PydanticObjectId,
        response_id: str,
        workspace_id: PydanticObjectId,
    ):
        await self._form_response_repo.delete_form_response(
            form_id=form_id, response_id=response_id
        )
        prefix = f"private/{workspace_id}/{form_id}/{response_id}"
        self._aws_service.delete_folder_from_s3(prefix)
        return response_id

    async def has_pending_deletion_request(self, form_id: str, response_id: str) -> bool:
        request = await self._form_response_repo.find_deletion_request_by_response_id(
            response_id
        )
        return bool(
            request
            and str(request.form_id) == str(form_id)
            and request.status == DeletionRequestStatus.PENDING
        )

    async def delete_response(self, response_id: str):
        return await self._form_response_repo.delete_response(response_id=response_id)

    async def get_by_uuid(self, workspace_id: PydanticObjectId, submission_uuid: str):
        response = await self._form_response_repo.get_by_submission_uuid(
            submission_uuid=submission_uuid
        )

        await self._form_response_repo.verify_response_exists_in_workspace(
            workspace_id=workspace_id, response_id=response.response_id
        )
        form = await self._form_repo.get_form_by_by_version(
            response.form_id, response.form_version if response.form_version else 1
        )
        if not form:
            form = await self._form_repo.get_form_document_by_id(response.form_id)

        workspace_form = await self._workspace_form_repo.find_first_by_form_id(
            form.form_id
        )
        form.settings = workspace_form.settings

        # The submission-number receipt is public by design (whoever holds
        # the number) — so it is always the respondent view: no internal
        # fields and no internal values, which are never even decrypted here.
        strip_internal_answers(response)
        decrypted_response = self.decrypt_form_response(
            workspace_id=workspace_id, response=response
        )
        respondent_response = StandardFormResponseCamelModel(
            **decrypted_response.model_dump(mode="json")
        )
        # Feedback is the respondent's to read here, like the answers: with
        # the workspace as the author, never the staff member.
        present_to_respondent(
            respondent_response,
            await self._workspace_title(workspace_id),
            enabled=bool(workspace_form.settings.respondent_feedback_enabled),
        )

        return {
            "form": respondent_view(
                StandardFormCamelModel(**form.model_dump(mode="json"))
            ),
            "response": respondent_response,
        }

    async def request_for_response_deletion_by_uuid(
        self, workspace_id, submission_uuid
    ):
        response = await self._form_response_repo.get_by_submission_uuid(
            submission_uuid
        )
        response_id = response.response_id
        await self._form_response_repo.verify_response_exists_in_workspace(
            workspace_id=workspace_id, response_id=response_id
        )
        deletion_request = (
            await self._form_response_repo.find_deletion_request_by_response_id(
                response_id
            )
        )
        if deletion_request:
            raise HTTPException(
                400,
                "Error: Deletion request already exists for the response : "
                + response_id,
            )

        await self._form_response_repo.add_deletion_request(response, response_id)
        pass

    async def internal_field_definitions(self, form_id: str) -> List[StandardFormField]:
        """The internal fields staff fill in on this form's submissions: those
        of the latest published version, or of the draft when the form was
        never published (the same form the dashboard shows)."""
        form = await self._form_repo.get_latest_version_of_form(form_id)
        if form is None:
            form = await self._form_repo.get_form_document_by_id(str(form_id))
        return internal_fields(form) if form else []

    async def all_internal_field_ids(
        self, form_id: str, every_version: bool = False
    ) -> Set[str]:
        """Ids that are internal in the draft or the latest published version
        — used to refuse respondent input for them whichever version the
        respondent was served.

        ``every_version`` adds every older published version too, for readers
        of stored answers (AI insights): an answer to a field that was
        internal when it was given stays staff-only even if the field is
        public now."""
        ids: Set[str] = set()
        versions = (
            await self._form_repo.get_versions_of_form(form_id)
            if every_version
            else [await self._form_repo.get_latest_version_of_form(form_id)]
        )
        draft = await self._form_repo.get_form_document_by_id(str(form_id))
        for form in (*versions, draft):
            if form is not None:
                ids |= internal_field_ids(form)
        return ids

    async def update_internal_answers(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        response_id: str,
        answers: Dict[str, Optional[Dict[str, Any]]],
        user: User,
        expected_version: Optional[int] = None,
    ) -> InternalAnswersResponse:
        """Staff fill in / edit / clear internal answers on one submission.

        Needs response.annotate (any active member today). Each changed answer records who changed
        it and when. Each answer is checked against its field's type and
        options (422 otherwise).

        Optimistic concurrency: ``expected_version`` is the
        ``internal_answers_version`` the editor loaded; the save only lands
        if nobody saved in between (409 with the current state otherwise).
        Without it, the read-modify-write below is still conditional on the
        version it read, so two simultaneous saves never lose one."""
        await self._authorization.authorize(
            user, Permission.RESPONSE_ANNOTATE, workspace_id
        )
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id, form_id
            )
        )
        if not workspace_form:
            raise HTTPException(
                HTTPStatus.NOT_FOUND, "Form not found in the workspace."
            )
        response = await self._form_response_repo.get_response(response_id)
        if not response or str(response.form_id) != str(workspace_form.form_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        if not answers:
            raise HTTPException(HTTPStatus.BAD_REQUEST, "No internal answers given.")

        definitions = fields_by_id(
            await self.internal_field_definitions(str(workspace_form.form_id))
        )
        unknown = [field_id for field_id in answers if field_id not in definitions]
        if unknown:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                f"'{unknown[0]}' is not an internal field of this form.",
            )

        validated = {
            field_id: (
                None
                if value is None
                else validate_internal_answer(definitions[field_id], value)
            )
            for field_id, value in answers.items()
        }

        stored_version = response.internal_answers_version or 0
        if expected_version is not None and expected_version != stored_version:
            raise self._internal_answers_conflict(workspace_id, response)

        current = self._decrypted_internal_answers(workspace_id, response)
        meta = dict(response.internal_answers_meta or {})
        now = dt.datetime.now(dt.timezone.utc)
        for field_id, value in validated.items():
            if value is None:
                current.pop(field_id, None)
            else:
                current[field_id] = value
            meta[field_id] = InternalAnswerMeta(
                updated_by=str(user.id), updated_by_email=user.sub, updated_at=now
            )

        response.internal_answers = crypto_service.encrypt(
            workspace_id=workspace_id,
            form_id=response.form_id,
            data=json.dumps(current),
        )
        response.internal_answers_meta = meta
        response.internal_answers_version = stored_version + 1
        saved = await self._form_response_repo.save_internal_answers(
            response, stored_version
        )
        if saved is None:
            latest = await self._form_response_repo.get_response(response_id)
            raise self._internal_answers_conflict(workspace_id, latest or response)
        return InternalAnswersResponse(
            internal_answers=current,
            internal_answers_meta=meta,
            internal_answers_version=stored_version + 1,
        )

    def _internal_answers_conflict(
        self, workspace_id: PydanticObjectId, response: StandardFormResponse
    ) -> HTTPException:
        """409 carrying the current state, so the editor can merge and retry."""
        latest = InternalAnswersResponse(
            internal_answers=self._decrypted_internal_answers(workspace_id, response),
            internal_answers_meta=response.internal_answers_meta or {},
            internal_answers_version=response.internal_answers_version or 0,
        )
        return HTTPException(
            HTTPStatus.CONFLICT,
            content={
                "message": "Another team member saved these internal fields "
                "just now. Review their changes and save again.",
                **latest.model_dump(mode="json", by_alias=True),
            },
        )

    def _decrypted_internal_answers(
        self, workspace_id: PydanticObjectId, response: StandardFormResponse
    ) -> Dict[str, Any]:
        stored = response.internal_answers
        if isinstance(stored, (bytes, str)):
            stored = json.loads(
                crypto_service.decrypt(
                    workspace_id=workspace_id, form_id=response.form_id, data=stored
                )
            )
        return {
            key: (
                value.model_dump(mode="json", exclude_none=True)
                if isinstance(value, StandardFormResponseAnswer)
                else value
            )
            for key, value in (stored or {}).items()
        }

    def file_download_url(self, workspace_id, form_id, response_id, file_id) -> str:
        """A download link for an uploaded answer file, signed for the key the
        file is actually stored under: the response's own folder (submissions),
        the shared private folder (older edits) or the bare id (oldest uploads).
        An empty string when the file is in none of them."""
        if not is_plain_file_id(file_id):
            return ""
        for key in (
            f"private/{workspace_id}/{form_id}/{response_id}/{file_id}",
            f"private/{file_id}",
            str(file_id),
        ):
            if self._aws_service.check_if_key_exists(key):
                return self._aws_service.generate_presigned_url(key=key)
        return ""

    def generate_presigned_url_for_each_response(
        self,
        file_fields: List[StandardFormField],
        response: StandardFormResponse,
        workspace_id: PydanticObjectId,
    ):
        for field in file_fields:
            file_answer = response.answers.get(field.id, {})
            if file_answer and file_answer.get("file_metadata") is not None:
                file_id = file_answer.get("file_metadata", {}).get("id", "")
                response.answers[field.id]["file_metadata"]["url"] = (
                    self.file_download_url(
                        workspace_id, response.form_id, response.response_id, file_id
                    )
                )
        return response


def get_fields_from_form(form: StandardFormCamelModel) -> List[StandardFormField]:
    fields = []
    if form.builder_version == "v2":
        for slide in form.fields:
            for field in slide.properties.fields:
                fields.append(field)
    else:
        for field in form.fields:
            fields.append(field)
    return fields


def get_fields_of_type_file_upload(form: StandardFormCamelModel):
    file_fields = []
    form_fields = get_fields_from_form(form)
    if form_fields:
        for field in form_fields:
            if (
                field.type == StandardFormFieldType.FILE_UPLOAD
                or field.type == StandardFormFieldType.INPUT_FILE_UPLOAD
            ):
                file_fields.append(field)
    return file_fields
