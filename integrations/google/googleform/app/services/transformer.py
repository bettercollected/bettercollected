from typing import Any, Dict, List

from beanie import PydanticObjectId
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
    LayoutType,
    WelcomePageField,
    ThankYouPageField,
    Theme,
)
from common.services.transformer_service import (
    FormTransformerService,
)

from googleform.app.exceptions import HTTPException
from googleform.app.models.google_form import GoogleFormDto, GoogleFormItemsDto
from googleform.app.models.google_form_response import (
    GoogleAnswer,
    GoogleFormResponseDto,
)

from loguru import logger

default_image_url = (
    "https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png"
)


class GoogleFormTransformerService(FormTransformerService):
    def _transform_field(self, index, item: GoogleFormItemsDto) -> StandardFormField:
        slide = StandardFormField()
        slide.id = str(PydanticObjectId())
        slide.index = index
        slide.type = StandardFormFieldType.SLIDE
        slide.image_url = default_image_url
        slide.properties.layout = LayoutType.TWO_COLUMN_IMAGE_RIGHT
        field = StandardFormField()
        field.title = item.title
        field.description = item.description
        field.index = 0

        if item.questionItem and item.questionItem.question:
            # Return rest of the field if it does not match the above conditions
            field.id = item.questionItem.question.questionId
            field.validations.required = item.questionItem.question.required
            question = item.questionItem.question
            if item.questionItem.image:
                slide.image_url = item.questionItem.image.contentUri
            if question.textQuestion and question.textQuestion.get("paragraph"):
                field.type = StandardFormFieldType.LONG_TEXT
            elif question.choiceQuestion:
                if question.choiceQuestion.type == "RADIO":
                    field.type = StandardFormFieldType.MULTIPLE_CHOICE
                    field.properties.allow_multiple_selection = False
                    field.properties.choices = [
                        StandardChoice(
                            value=option.get("value"), id=str(PydanticObjectId())
                        )
                        for option in question.choiceQuestion.options
                        if option.get("value")
                    ]
                elif question.choiceQuestion.type == "CHECKBOX":
                    field.type = StandardFormFieldType.MULTIPLE_CHOICE
                    field.properties.allow_multiple_selection = True
                    field.properties.choices = [
                        StandardChoice(
                            value=option.get("value"), id=str(PydanticObjectId())
                        )
                        for option in question.choiceQuestion.options
                        if option.get("value")
                    ]
                elif question.choiceQuestion.type == "DROP_DOWN":
                    field.type = StandardFormFieldType.DROPDOWN
                    field.properties.allow_multiple_selection = False
                    field.properties.choices = [
                        StandardChoice(
                            value=option.get("value"), id=str(PydanticObjectId())
                        )
                        for option in question.choiceQuestion.options
                        if option.get("value")
                    ]
            elif question.fileUploadQuestion:
                field.type = StandardFormFieldType.FILE_UPLOAD
            elif question.scaleQuestion:
                field.type = StandardFormFieldType.LINEAR_RATING
                field.properties.start_from = question.scaleQuestion.get("low", 0)
                field.properties.steps = question.scaleQuestion.get("high", 0)
            elif question.dateQuestion:
                field.type = StandardFormFieldType.DATE
                field.properties.date_format = "mm/dd/yyyy"
                # TODO: Fix for time and year, and add for timeQuestion
            else:
                field.type = StandardFormFieldType.SHORT_TEXT

        elif item.questionGroupItem:
            if item.questionGroupItem.image:
                slide.image_url = item.questionGroupItem.image.contentUri

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
            slide.image_url = item.imageItem.image.contentUri
            field.attachment = StandardFieldAttachment(
                type=StandardAttachmentType.IMAGE, href=item.imageItem.image.contentUri
            )

        elif item.videoItem:
            field.attachment = StandardFieldAttachment(
                type=StandardAttachmentType.VIDEO,
                href=item.videoItem.video.youtubeUri,
                embed_provider=EmbedProvider.YOUTUBE,
            )

        slide.properties.fields = [field]
        return slide, field

    def _transform_fields(self, fields: List[GoogleFormItemsDto]):
        index = 0
        temp_text_fields: List[GoogleFormItemsDto] = []
        temp_text_field_index = 0
        transform_fields = []
        slide_and_field_list = []
        for field in fields:
            if field.textItem is not None or field.pageBreakItem is not None:
                if index < (len(fields) - 1):
                    text_field = StandardFormField()
                    text_field.title = field.title
                    text_field.id = field.itemId
                    text_field.type = StandardFormFieldType.TEXT
                    text_field.index = len(temp_text_fields)
                    temp_text_fields.append(text_field)
                    temp_text_field_index = index
                continue
            slide, updated_field = self._transform_field(index, field)
            slide_and_field_list.append(slide.id)
            slide_and_field_list.append(updated_field.id)
            # slide_and_field_list.append(updated_field.type if updated_field.type else "")
            if len(temp_text_fields) > 0:
                slide.properties.fields[0].index = len(temp_text_fields)
                slide.properties.fields = temp_text_fields + slide.properties.fields
                temp_text_fields = []
            transform_fields.append(slide)
            index += 1
        if len(temp_text_fields) > 0:
            slide, updated_field = self._transform_field(
                index, fields[temp_text_field_index]
            )
            transform_fields.append(slide)
            slide_and_field_list.append(slide.id)
            slide_and_field_list.append(updated_field.id)
            # slide_and_field_list.append(updated_field.type if updated_field.type else "")
        return transform_fields, slide_and_field_list

    def _transform_welcome_page(self, welcome_page_title):
        return WelcomePageField(
            title=welcome_page_title,
            layout=LayoutType.TWO_COLUMN_IMAGE_RIGHT,
            imageUrl=default_image_url,
        )

    def _transform_thank_you_page(self):
        return [
            ThankYouPageField(
                layout=LayoutType.TWO_COLUMN_IMAGE_RIGHT, imageUrl=default_image_url
            )
        ]

    def _transform_theme(self):
        return Theme(
            title="Default",
            primary="#2E2E2E",
            secondary="#0764EB",
            tertiary="#A2C5F8",
            accent="#F2F7FF",
        )

    def _transform_welcome_page(self, welcome_page_title):
        return WelcomePageField(
            title=welcome_page_title,
            layout=LayoutType.TWO_COLUMN_IMAGE_RIGHT,
            imageUrl=default_image_url,
        )

    def _transform_thank_you_page(self):
        return [
            ThankYouPageField(
                layout=LayoutType.TWO_COLUMN_IMAGE_RIGHT, imageUrl=default_image_url
            )
        ]

    def _transform_theme(self):
        return Theme(
            title="Default",
            primary="#2E2E2E",
            secondary="#0764EB",
            tertiary="#A2C5F8",
            accent="#F2F7FF",
        )

    def transform_form(self, form: Dict[str, Any]) -> StandardForm:
        try:
            googleform = GoogleFormDto(**form)
            slides, slide_and_field_list = self._transform_fields(googleform.items)
            standard_form = StandardForm(
                builder_version="v2",
                form_id=str(PydanticObjectId()),
                imported_form_id=googleform.formId,
                title=googleform.info.documentTitle or "Untitled",
                description=googleform.info.description,
                fields=slides,
                settings=self._transform_form_settings(googleform),
                is_multi_page=True,
                welcome_page=(
                    self._transform_welcome_page(googleform.info.title or "Untitled")
                ),
                thankyou_page=(self._transform_thank_you_page()),
                theme=(self._transform_theme()),
            )
            return standard_form, slide_and_field_list
        except Exception as error:
            logger.error(f"Error transforming single form: {error}")
            raise HTTPException(
                status_code=500, content=f"Google data transformation failed. {error}"
            )

    def transform_form_responses(
        self,
        responses: List[Dict[str, Any]],
        standard_form: StandardForm,
        slide_and_field_list: List[Any],
    ) -> List[StandardFormResponse]:
        standard_form_responses = [
            self.transform_single_form_response(
                response, standard_form, slide_and_field_list
            )
            for response in responses
        ]
        return standard_form_responses

    def transform_single_form_response(
        self,
        google_response_data: Dict[str, Any],
        standard_form: StandardForm,
        slide_and_field_list: List[Any],
    ) -> StandardFormResponse:
        try:
            google_response = GoogleFormResponseDto(**google_response_data)
            response = StandardFormResponse(
                response_id=google_response.responseId,
                provider=FormProvider.GOOGLE,
                respondent_email=google_response.respondentEmail,
                created_at=google_response.createTime,
                updated_at=google_response.lastSubmittedTime,
                answers=self._transform_answers(
                    google_response.answers, standard_form, slide_and_field_list
                ),
            )
            if google_response.respondentEmail is not None:
                response.dataOwnerIdentifier = google_response.respondentEmail
            return response
        except Exception as error:
            logger.error(f"Error transforming single form response: {error}")
            raise HTTPException(
                status_code=500, content=f"Google data transformation failed. {error}"
            )

    def _transform_answers(
        self,
        answers: Dict[str, GoogleAnswer],
        standard_form: StandardForm,
        slide_and_field_list: List[Any],
    ):
        standard_answers = {}
        if answers is None:
            return standard_answers
        for question_id, answer in answers.items():
            standard_answers[question_id] = self._transform_answer(
                answer,
                [
                    field
                    for field in standard_form.fields
                    if field.id
                    == slide_and_field_list[slide_and_field_list.index(question_id) - 1]
                ],
            )
        return standard_answers

    def _transform_answer(
        self,
        answer: GoogleAnswer,
        standard_field: List[StandardFormField],
    ) -> StandardFormResponseAnswer:
        standard_answer = StandardFormResponseAnswer()
        field = standard_field[0].properties.fields[-1]
        if answer.textAnswers and len(answer.textAnswers.answers) > 0:
            if field.type == StandardFormFieldType.MULTIPLE_CHOICE:
                choice_answers = answer.textAnswers.answers
                if field.properties.allow_multiple_selection:
                    choice_ids = []
                    for answer in choice_answers:
                        choice_ids.append(
                            [
                                choice.id
                                for choice in field.properties.choices
                                if choice.value == answer.value
                            ][0]
                        )
                    standard_answer.choices = StandardChoicesAnswer(values=choice_ids)
                else:
                    choice_id = [
                        choice.id
                        for choice in field.properties.choices
                        if choice.value == choice_answers[0].value
                    ][0]
                    standard_answer.choice = StandardChoiceAnswer(value=choice_id)
            elif field.type == StandardFormFieldType.LINEAR_RATING:
                standard_answer.number = answer.textAnswers.answers[0].value
            elif (
                field.type == StandardFormFieldType.SHORT_TEXT
                or field.type == StandardFormFieldType.LONG_TEXT
            ):
                standard_answer.text = answer.textAnswers.answers[0].value
            elif field.type == StandardFormFieldType.DATE:
                standard_answer.date = answer.textAnswers.answers[0].value
            elif field.type == StandardFormFieldType.DROPDOWN:
                choice_id = [
                    choice.id
                    for choice in field.properties.choices
                    if choice.value == answer.textAnswers.answers[0].value
                ][0]
                standard_answer.choice = StandardChoiceAnswer(value=choice_id)
            # elif answer.textAnswers.answers:
            #     standard_answer.text = answer.textAnswers.answers[0].value
            #     standard_answer.choice = StandardChoiceAnswer(
            #         value=answer.textAnswers.answers[0].value
            #     )
            #     standard_answer.choices = StandardChoicesAnswer(
            #         values=[choice.value for choice in answer.textAnswers.answers]
            #     )

        return standard_answer

    @staticmethod
    def _transform_form_settings(googleform: GoogleFormDto):
        setting = StandardFormSettings()
        setting.provider = "self"
        setting.custom_url = googleform.formId
        setting.embed_url = googleform.responderUri
        setting.is_public = True
        return setting
