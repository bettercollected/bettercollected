from typing import Any, Dict, List

from loguru import logger

from common.enums.form_provider import FormProvider
from common.models.standard_form import (
    EmbedProvider,
    StandardAttachmentType,
    StandardChoice,
    StandardChoiceAnswer,
    StandardChoicesAnswer,
    StandardFieldAttachment,
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
    StandardFormResponse,
    StandardFormResponseAnswer,
    StandardFormSettings,
)
from common.services.transformer_service import (
    FormDocumentType,
    FormResponseDocumentType,
    FormTransformerService,
)
from googleform.app.exceptions import HTTPException
from googleform.app.models.google_form import GoogleFormDto, GoogleFormItemsDto
from googleform.app.models.google_form_response import (
    GoogleAnswer,
    GoogleFormResponseDto,
)


class GoogleFormTransformerService(FormTransformerService):
    def _transform_field(self, item: GoogleFormItemsDto) -> StandardFormField:
        field = StandardFormField()
        field.title = item.title
        field.description = item.description

        if item.questionItem and item.questionItem.question:
            # Return rest of the field if it does not match the above conditions
            field.id = item.questionItem.question.questionId
            field.validations.required = item.questionItem.question.required
            question = item.questionItem.question
            if question.textQuestion and question.textQuestion.get("paragraph"):
                field.type = StandardFormFieldType.LONG_TEXT
            elif question.choiceQuestion:
                if question.choiceQuestion.type == "RADIO":
                    field.type = StandardFormFieldType.MULTIPLE_CHOICE
                    field.properties.allow_multiple_selection = False
                    field.properties.choices = [
                        StandardChoice(label=option.get("value"))
                        for option in question.choiceQuestion.options
                        if option.get("value")
                    ]
                elif question.choiceQuestion.type == "CHECKBOX":
                    field.type = StandardFormFieldType.MULTIPLE_CHOICE
                    field.properties.allow_multiple_selection = True
                    field.properties.choices = [
                        StandardChoice(label=option.get("value"))
                        for option in question.choiceQuestion.options
                        if option.get("value")
                    ]
                elif question.choiceQuestion.type == "DROP_DOWN":
                    field.type = StandardFormFieldType.DROPDOWN
                    field.properties.allow_multiple_selection = False
                    field.properties.choices = [
                        StandardChoice(label=option.get("value"))
                        for option in question.choiceQuestion.options
                        if option.get("value")
                    ]
            elif question.fileUploadQuestion:
                field.type = StandardFormFieldType.FILE_UPLOAD
            elif question.scaleQuestion:
                field.type = StandardFormFieldType.OPINION_SCALE
                field.properties.start_form = question.scaleQuestion.get("low", 0)
                field.properties.steps = question.scaleQuestion.get("high", 0)
            elif question.dateQuestion:
                field.type = StandardFormFieldType.DATE
                field.properties.date_format = "mm/dd/yyyy"
                # TODO: Fix for time and year, and add for timeQuestion
            else:
                field.type = StandardFormFieldType.SHORT_TEXT

        elif item.questionGroupItem:
            field.type = StandardFormFieldType.MATRIX
            field.properties.fields = [
                StandardFormField(
                    id=question.questionId,
                    title=question.rowQuestion.title,
                    properties=StandardFieldProperty(
                        allow_multiple_selection=item.questionGroupItem.grid.columns.type
                        == "CHECKBOX",
                        choices=[
                            StandardChoice(label=option.value)
                            for option in item.questionGroupItem.grid.columns.options
                        ],
                    ),
                )
                for question in item.questionGroupItem.questions
            ]

        elif item.imageItem:
            field.attachment = StandardFieldAttachment(
                type=StandardAttachmentType.IMAGE, href=item.imageItem.image.contentUri
            )
        elif item.videoItem:
            field.attachment = StandardFieldAttachment(
                type=StandardAttachmentType.VIDEO,
                href=item.videoItem.video.youtubeUri,
                embed_provider=EmbedProvider.YOUTUBE,
            )
        return field

    def _transform_fields(self, fields: List[GoogleFormItemsDto]):
        transform_fields = list(map(self._transform_field, fields))
        return transform_fields

    def transform_form(self, form: Dict[str, Any]) -> StandardForm:
        try:
            googleform = GoogleFormDto(**form)
            standard_form = StandardForm(
                form_id=googleform.formId,
                title=googleform.info.title,
                description=googleform.info.description,
                fields=self._transform_fields(googleform.items),
                settings=self._transform_form_settings(googleform),
            )
            return standard_form
        except Exception as error:
            logger.error(f"Error transforming single form: {error}")
            raise HTTPException(
                status_code=500, content=f"Google data transformation failed. {error}"
            )

    def transform_form_responses(
        self, responses: List[Dict[str, Any]]
    ) -> List[StandardFormResponse]:
        standard_form_responses = [
            self.transform_single_form_response(response) for response in responses
        ]
        return standard_form_responses

    def transform_single_form_response(
        self, google_response_data: Dict[str, Any]
    ) -> StandardFormResponse:
        try:
            google_response = GoogleFormResponseDto(**google_response_data)
            response = StandardFormResponse(
                response_id=google_response.responseId,
                provider=FormProvider.GOOGLE,
                created_at=google_response.createTime,
                updated_at=google_response.lastSubmittedTime,
                answers=self._transform_answers(google_response.answers),
            )
            return response
        except Exception as error:
            logger.error(f"Error transforming single form response: {error}")
            raise HTTPException(
                status_code=500, content=f"Google data transformation failed. {error}"
            )

    def _transform_answers(self, answers: Dict[str, GoogleAnswer]):
        standard_answers = {}
        for question_id, answer in answers.items():
            standard_answers[question_id] = self._transform_answer(answer)
        return standard_answers

    def _transform_answer(self, answer: GoogleAnswer) -> StandardFormResponseAnswer:
        standard_answer = StandardFormResponseAnswer()

        if answer.textAnswers and len(answer.textAnswers.answers) > 0:
            if len(answer.textAnswers.answers) > 1:
                standard_answer.choices = StandardChoicesAnswer(
                    values=[choice.value for choice in answer.textAnswers.answers]
                )
            elif answer.textAnswers.answers:
                standard_answer.text = answer.textAnswers.answers[0].value
                standard_answer.choice = StandardChoiceAnswer(
                    value=answer.textAnswers.answers[0].value
                )
                standard_answer.choices = StandardChoicesAnswer(
                    values=[choice.value for choice in answer.textAnswers.answers]
                )

        return standard_answer

    @staticmethod
    def _transform_form_settings(googleform: GoogleFormDto):
        setting = StandardFormSettings()
        setting.provider = FormProvider.GOOGLE
        setting.custom_url = googleform.formId
        setting.embed_url = googleform.responderUri
        setting.is_public = True
        return setting
