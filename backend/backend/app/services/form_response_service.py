import datetime as dt
import json
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Sequence, Set

from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN, MESSAGE_NOT_FOUND
from common.models.standard_form import (
    InternalAnswerMeta,
    StandardAnswerField,
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
from backend.app.models.dtos.response_dtos import (
    StandardFormCamelModel,
    StandardFormFieldCamelModel,
    StandardFormResponseCamelModel,
)
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.standard_form_response import (
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.internal_fields import (
    fields_by_id,
    internal_field_ids,
    internal_fields,
    strip_internal_answers,
    strip_internal_fields,
)
from backend.app.utils.hash import hash_string


class FormResponseService:
    def __init__(
        self,
        form_response_repo: FormResponseRepository,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
        workspace_user_repo: WorkspaceUserRepository,
        aws_service: AWSS3Service,
    ):
        self._form_response_repo = form_response_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self._workspace_user_repo = workspace_user_repo
        self._aws_service = aws_service

    async def get_all_workspace_responses(
        self,
        workspace_id: PydanticObjectId,
        filter_query: FormResponseFilterQuery,
        sort: SortRequest,
        request_for_deletion: bool,
        user: User,
        data_subjects: bool = None,
    ):
        if not await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
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
        # A respondent's own listing never carries staff-entered values.
        for item in user_responses.items:
            strip_internal_answers(item)
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
        if not await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
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

    async def get_workspace_form_all_submissions(
        self, form_id: str, workspace_id: PydanticObjectId, user: User
    ):
        if not await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )
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
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
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
            strip_internal_fields(form)
        response.form_title = form.title
        decrypted_response = self.decrypt_form_response(
            workspace_id=workspace_id, response=response
        )
        for key, decrypted_answer in decrypted_response.answers.items():
            decrypted_answer = (
                decrypted_answer.model_dump(mode="json")
                if isinstance(decrypted_answer, StandardFormResponseAnswer)
                else decrypted_answer
            )
            if decrypted_answer.get("file_metadata") is not None:
                file_url = self._aws_service.generate_presigned_url(
                    decrypted_answer["file_metadata"].get("id")
                )
                decrypted_response.answers[key]["file_metadata"]["url"] = file_url

        return SingleSubmissionResponse(
            form=form,
            response=decrypted_response,
            internal_fields=staff_internal_fields,
        )

    async def request_for_response_deletion(
        self, workspace_id: PydanticObjectId, response_id: str, user: User
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        )
        # TODO : Handle case for multiple form import by other user
        response = await self._form_response_repo.get_response(response_id)

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
        return updated_response.response_uuid

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

        return {
            "form": strip_internal_fields(
                StandardFormCamelModel(**form.model_dump(mode="json"))
            ),
            "response": StandardFormResponseCamelModel(
                **decrypted_response.model_dump(mode="json")
            ),
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

    async def all_internal_field_ids(self, form_id: str) -> Set[str]:
        """Ids that are internal in the draft or the latest published version
        — used to refuse respondent input for them whichever version the
        respondent was served."""
        ids: Set[str] = set()
        latest = await self._form_repo.get_latest_version_of_form(form_id)
        draft = await self._form_repo.get_form_document_by_id(str(form_id))
        for form in (latest, draft):
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
    ) -> InternalAnswersResponse:
        """Staff fill in / edit / clear internal answers on one submission.

        Any active workspace member may do this — the same access that lets
        them edit the form itself. Each changed answer records who changed
        it and when."""
        if not await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        ):
            raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)
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

        current = self._decrypted_internal_answers(workspace_id, response)
        meta = dict(response.internal_answers_meta or {})
        now = dt.datetime.now(dt.timezone.utc)
        for field_id, value in answers.items():
            if value is None:
                current.pop(field_id, None)
            else:
                current[field_id] = _validated_internal_answer(field_id, value)
            meta[field_id] = InternalAnswerMeta(
                updated_by=str(user.id), updated_by_email=user.sub, updated_at=now
            )

        response.internal_answers = crypto_service.encrypt(
            workspace_id=workspace_id,
            form_id=response.form_id,
            data=json.dumps(current),
        )
        response.internal_answers_meta = meta
        await self._form_response_repo.save(response)
        return InternalAnswersResponse(
            internal_answers=current, internal_answers_meta=meta
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
                private_key = f"private/{workspace_id}/{response.form_id}/{response.response_id}/{file_id}"
                key_exists = self._aws_service.check_if_key_exists(private_key)
                if key_exists:
                    url = self._aws_service.generate_presigned_url(key=private_key)
                else:
                    key = file_answer.get("file_metadata", {}).get("id", "")
                    url = (
                        self._aws_service.generate_presigned_url(key=key) if key else ""
                    )
                response.answers[field.id]["file_metadata"]["url"] = url
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


# One internal answer is a short staff note, never a document: cap its size so
# the endpoint can't be used to park arbitrary payloads on a response.
MAX_INTERNAL_ANSWER_BYTES = 10_000


def _validated_internal_answer(field_id: str, value: Dict[str, Any]) -> Dict[str, Any]:
    try:
        answer = StandardFormResponseAnswer.model_validate(value)
    except ValueError:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, f"Invalid answer for internal field '{field_id}'."
        )
    answer.field = StandardAnswerField(id=field_id)
    dumped = answer.model_dump(mode="json", exclude_none=True)
    if len(json.dumps(dumped)) > MAX_INTERNAL_ANSWER_BYTES:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            f"The answer for internal field '{field_id}' is too long.",
        )
    return dumped
