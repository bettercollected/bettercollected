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
from loguru import logger

from googleform.app.exceptions import HTTPException
from googleform.app.models.google_form import GoogleFormDto, GoogleFormItemsDto
from googleform.app.models.google_form_response import (
    GoogleAnswer,
    GoogleFormResponseDto,
)

default_image_url = (
    "https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png"
)


class GoogleFormTransformerService(FormTransformerService):
    def _transform_field(
        self, slide: StandardFormField, item: GoogleFormItemsDto
    ) -> StandardFormField:
        field = StandardFormField()
        field.title = item.title
        field.description = item.description

        if item.questionItem and item.questionItem.question:
            # Return rest of the field if it does not match the above conditions
            field.id = item.questionItem.question.questionId
            field.validations.required = item.questionItem.question.required
            question = item.questionItem.question
            if item.questionItem.image:
                field.image_url = item.questionItem.image.contentUri
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
            field.id = item.itemId
            if item.questionGroupItem.image:
                field.image_url = item.questionGroupItem.image.contentUri

            field.type = StandardFormFieldType.MATRIX
            field.properties.allow_multiple_selection = item.questionGroupItem.grid.columns.type == "CHECKBOX"
            field.properties.fields = [
                StandardFormField(
                    id=question.questionId,
                    title=question.rowQuestion.title,
                    type=StandardFormFieldType.MULTIPLE_CHOICE,
                    properties=StandardFieldProperty(
                        allow_multiple_selection=item.questionGroupItem.grid.columns.type
                        == "CHECKBOX",
                        choices=[
                            StandardChoice(label=option.value, id=str(PydanticObjectId()), value=option.value)
                            for option in item.questionGroupItem.grid.columns.options
                        ],
                    ),
                )
                for question in item.questionGroupItem.questions
            ]

        elif item.imageItem:
            field.id = item.itemId
            field.type = StandardFormFieldType.IMAGE_CONTENT
            field.attachment = StandardFieldAttachment(
                type=StandardAttachmentType.IMAGE, href=item.imageItem.image.contentUri
            )

        elif item.videoItem:
            field.id = item.itemId
            field.type = StandardFormFieldType.VIDEO_CONTENT
            field.attachment = StandardFieldAttachment(
                type=StandardAttachmentType.VIDEO,
                href=item.videoItem.video.youtubeUri,
                embed_provider=EmbedProvider.YOUTUBE,
            )

        elif item.textItem is not None:
            field.id = item.itemId
            field.type = StandardFormFieldType.TEXT

        field_index = len(slide.properties.fields)
        field.index = field_index
        slide.properties.fields.append(field)

        return slide, field

    def create_new_slide(self, index: int):
        slide = StandardFormField()
        slide.id = str(PydanticObjectId())
        slide.index = index
        slide.type = StandardFormFieldType.SLIDE
        slide.image_url = default_image_url
        slide.properties.layout = LayoutType.TWO_COLUMN_IMAGE_RIGHT
        slide.properties.fields = []
        return slide

    def create_new_slide_with_text_field(
        self, google_field: GoogleFormItemsDto, index: int
    ):
        text_field = StandardFormField()
        text_field.title = google_field.title
        text_field.id = google_field.itemId
        text_field.type = StandardFormFieldType.TEXT
        text_field.index = 0
        new_slide = self.create_new_slide(index)
        new_slide.properties.fields.append(text_field)
        return new_slide

    def _transform_fields(self, fields: List[GoogleFormItemsDto]):
        transform_fields = []
        field_id_and_fields_map = {}
        active_slide = self.create_new_slide(0)
        for google_field in fields:
            if google_field.pageBreakItem is not None:
                transform_fields.append(active_slide)
                active_slide = self.create_new_slide_with_text_field(
                    google_field, len(transform_fields)
                )
                continue
            active_slide, field = self._transform_field(active_slide, google_field)
            if field.type == StandardFormFieldType.MATRIX:
                for row in field.properties.fields:
                    field_id_and_fields_map[row.id] = row
            else:
                field_id_and_fields_map[field.id] = field
        transform_fields.append(active_slide)
        return transform_fields, field_id_and_fields_map

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
            slides, field_id_and_fields_map = self._transform_fields(googleform.items)
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
            return standard_form, field_id_and_fields_map
        except Exception as error:
            logger.error(f"Error transforming single form: {error}")
            raise HTTPException(
                status_code=500, content=f"Google data transformation failed. {error}"
            )

    def transform_form_responses(
        self,
        responses: List[Dict[str, Any]],
        field_id_and_fields_map: List[Any],
    ) -> List[StandardFormResponse]:
        standard_form_responses = [
            self.transform_single_form_response(response, field_id_and_fields_map)
            for response in responses
        ]
        return standard_form_responses

    def transform_single_form_response(
        self,
        google_response_data: Dict[str, Any],
        field_id_and_fields_map: List[Any],
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
                    google_response.answers, field_id_and_fields_map
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
        field_id_and_fields_map: Dict[str, StandardFormField],
    ):
        standard_answers = {}
        if answers is None:
            return standard_answers
        for question_id, answer in answers.items():
            if field_id_and_fields_map.get(question_id, None) is not None:
                standard_answers[question_id] = self._transform_answer(
                    answer,
                    field_id_and_fields_map.get(question_id),
                )
        return standard_answers

    def _transform_answer(
        self,
        answer: GoogleAnswer,
        field: StandardFormField,
    ) -> StandardFormResponseAnswer:
        standard_answer = StandardFormResponseAnswer()
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


        return standard_answer

    @staticmethod
    def _transform_form_settings(googleform: GoogleFormDto):
        setting = StandardFormSettings()
        setting.provider = "self"
        setting.custom_url = googleform.formId
        setting.embed_url = googleform.responderUri
        setting.is_public = True
        return setting
