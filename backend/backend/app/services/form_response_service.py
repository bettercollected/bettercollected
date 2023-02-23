from http import HTTPStatus

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_UNAUTHORIZED
from common.models.standard_form import StandardFormDto, StandardFormResponseDto, StandardFormResponseTransformerDto
from common.models.user import User
from common.utils.logger import logger


class FormResponseService:
    def __init__(
            self,
            form_response_repo: FormResponseRepository,
            workspace_form_repo: WorkspaceFormRepository,
            workspace_user_repo: WorkspaceUserRepository,
    ):
        self._form_response_repo = form_response_repo
        self._workspace_form_repo = workspace_form_repo
        self._workspace_user_repo = workspace_user_repo

    async def get_workspace_submissions(
            self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        try:
            if not await self._workspace_user_repo.is_user_admin_in_workspace(
                    workspace_id, user
            ):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_UNAUTHORIZED
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
            # TODO : Refactor with mongo query instead of python
            form_responses = await self._form_response_repo.list(form_id)
            return form_responses
        except Exception as exc:
            logger.error(exc)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_workspace_submission(
            self, workspace_id: PydanticObjectId, response_id: str, user: User
    ):
        # TODO : Handle is_admin by decorator
        if not await self._workspace_user_repo.is_user_admin_in_workspace(
                workspace_id, user
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_UNAUTHORIZED
            )
        # TODO : Handle case for multiple form import by other user
        response = await FormResponseDocument.find_one({"responseId": response_id})
        form = await FormDocument.find_one({"formId": response.formId})
        workspace_form = await WorkspaceFormDocument.find({
            "workspace_id": workspace_id,
            "form_id": form.formId,
        }).to_list()
        if not workspace_form:
            raise HTTPException(404, "Form not found in this workspace")
        workspace_user = await WorkspaceUserDocument.find_one(
            {"workspace_id": workspace_id, "user_id": PydanticObjectId(user.id)})
        if not (workspace_user or response['dataOwnerIdentifier'] == user.sub):
            raise HTTPException(403, "You are not authorized to perform this action.")

        response.formTitle = form.title

        # TODO : Refactor/Remove and transform at early stage while saving
        mapped_form_response = FormResponseService._map_typeform_form_and_response(form, response)
        return mapped_form_response
        # try:
        #     workspace_form = (
        #         await self._workspace_form_repo.get_workspace_form_in_workspace(
        #             workspace_id, form_id
        #         )
        #     )
        #     if not workspace_form:
        #         raise HTTPException(
        #             HTTPStatus.NOT_FOUND, "Form not found in the workspace."
        #         )
        #     form_response = await self._form_response_repo.get(form_id, response_id)
        #     return form_response
        # except Exception as exc:
        #     logger.error(exc)
        #     raise HTTPException(
        #         status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        #         content=MESSAGE_DATABASE_EXCEPTION,
        #     )

    @staticmethod
    def _map_typeform_form_and_response(form: StandardFormDto,
                                        response: StandardFormResponseDto) -> StandardFormResponseTransformerDto:
        mapped_form_response = StandardFormResponseTransformerDto(**form.dict())
        mapped_form_response.responseId = response.responseId
        mapped_form_response.provider = response.provider
        mapped_form_response.dataOwnerIdentifierType = response.dataOwnerIdentifierType
        mapped_form_response.dataOwnerIdentifier = response.dataOwnerIdentifier
        mapped_form_response.responseCreatedAt = response.createdAt
        mapped_form_response.responseUpdatedAt = response.updatedAt

        mapped_question_answers = []
        for question in mapped_form_response.questions:
            question_id = question.questionId
            if question.isGroupQuestion and question.type and question.type.get('questions'):
                if not question.type.get('type') == "GROUP":
                    answer = []
                    for t in question.type.get('questions'):
                        ques_id = t['questionId']
                        ques = {'questionId': ques_id}
                        if response.responses.get(ques_id) and response.responses.get(ques_id).answer:
                            ques['answer'] = response.responses.get(ques_id).answer
                        answer.append(ques)
                    question.answer = answer
                else:
                    answers = []
                    # TODO: don't hardcode strings in new repo, convert to DTOs
                    if question.type.get('questions') is None:
                        answer_field = response.responses.get(question.questionId)
                        question.answer = answer_field.answer if answer_field else None
                    else:
                        for sub_question in question.type['questions']:
                            answer_field = response.responses.get(sub_question.get('questionId'))

                            if sub_question.get('type').get('type') == "RADIO":
                                answer = answer_field.answer[0].get('value') if answer_field.answer else None
                            elif sub_question.get('type').get('type') == "CHECKBOX":
                                answer = []
                                for a in answer_field.answer:
                                    answer.append(a.get("value") if type(a) is dict else a)
                            else:
                                answer = answer_field.answer if answer_field else ""
                            answers.append({"answer": answer,
                                            "questionId": sub_question.get('questionId')})
                    question.answer = answers

            else:
                if response.responses.get(question_id) and response.responses.get(question_id).answer and type(
                        response.responses.get(question_id).answer) is list:
                    answer = []
                    for a in response.responses.get(question_id).answer:
                        answer.append(a.get("value") if type(a) is dict else a)
                    question.answer = answer
                elif response.responses.get(question_id) and response.responses.get(
                        question_id).answer and not response.responses.get(question_id).answer:
                    question.answer = response.responses.get(question_id).answer
                elif response.responses.get(question_id) and response.responses.get(
                        question_id).answer and response.responses.get(question_id).answer:
                    question.answer = response.responses.get(question_id).answer
                else:
                    question.answer = ''
            mapped_question_answers.append(question)
        mapped_form_response.questions = mapped_question_answers
        return mapped_form_response
