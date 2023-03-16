from typing import Any, Dict, List

from fastapi import HTTPException
from loguru import logger

from common.enums.form_provider import FormProvider
from common.models.standard_form import (
    StandardForm, StandardFormSettings, StandardFormField, StandardFieldAttachment, StandardAttachmentProperties,
    EmbedProvider, StandardFieldProperty, StandardFieldValidations, StandardChoice, StandardFormResponse,
    StandardFormResponseAnswer, StandardAnswerField, StandardChoiceAnswer, StandardChoicesAnswer, StandardPaymentAnswer,
    StandardFormFieldType)
from common.services.transformer_service import FormTransformerService
from typeform.app.models.typeform_models import \
    TypeFormField, Answer, Attachment, TypeFormResponse, TypeFormDto, FieldType, FieldProperties, Validation, Choice


class TypeFormTransformerService(FormTransformerService):

    def transform_form(self, form: Dict[str, Any]) -> StandardForm:
        try:
            typeform = TypeFormDto(**form)
            standard_form = StandardForm(
                form_id=typeform.id,
                title=typeform.title,
                type=typeform.type,
                fields=self._transform_fields(typeform.fields),
                settings=self._transform_form_settings(typeform)
            )
            return standard_form
        except Exception as error:
            logger.error(f"Error transforming single form response: {error}")
            raise HTTPException(status_code=500, detail=f"Data transformation failed. {error}")

    def transform_form_responses(self, responses: List[Dict[str, Any]]) -> List[StandardFormResponse]:
        standard_form_responses = [self.transform_single_form_response(response) for response in responses]
        return standard_form_responses

    def transform_single_form_response(self,
                                       response: Dict[str, Any]) -> StandardFormResponse:
        try:
            response = TypeFormResponse(**response)
            standard_form_response = StandardFormResponse(
                response_id=response.response_id,
                provider=FormProvider.TYPEFORM,
                answers=self._transform_answers(response.answers),
                created_at=response.landed_at,
                updated_at=response.submitted_at,
                published_at=response.submitted_at
            )
            return standard_form_response
        except Exception as error:
            logger.error(f"Error transforming single form response: {error}")
            raise HTTPException(status_code=500, detail=f"Data transformation failed. {error}")

    def _transform_fields(self, fields: List[TypeFormField]) -> List[StandardFormField]:
        transformed_fields = list(map(self._transform_field, fields))
        return transformed_fields

    @staticmethod
    def _transform_attachment(attachment: Attachment) -> StandardFieldAttachment:
        std_attachment = StandardFieldAttachment()
        std_attachment.type = attachment.type
        std_attachment.href = attachment.href
        std_attachment.properties = StandardAttachmentProperties(description=attachment.properties.description)
        if attachment.href:
            if EmbedProvider.YOUTUBE in attachment.href:
                std_attachment.embed_provider = EmbedProvider.YOUTUBE
            elif EmbedProvider.VIEMO in attachment.href:
                std_attachment.embed_provider = EmbedProvider.VIEMO
            else:
                std_attachment.embed_provider = EmbedProvider.NO_EMBED
        return std_attachment

    def _transform_field(self, typeform_field: TypeFormField) -> StandardFormField:
        standard_type = self._transform_type(typeform_field)
        standard_form_field = StandardFormField(
            id=typeform_field.id,
            ref=typeform_field.ref,
            title=typeform_field.title,
            description=typeform_field.properties.description,
            validations=self._transform_validations(typeform_field.validations),
            attachment=self._transform_attachment(typeform_field.attachment),
            properties=self._transform_properties(typeform_field.properties),
            type=standard_type
        )
        return standard_form_field

    @staticmethod
    def _transform_type(typeform_field: TypeFormField) -> StandardFormFieldType:
        match typeform_field.type:
            case FieldType.CONTACT_INFO | FieldType.ADDRESS:
                standard_type = StandardFormFieldType.GROUP
            case FieldType.EMAIL \
                 | FieldType.PHONE_NUMBER \
                 | FieldType.NUMBER \
                 | FieldType.WEBSITE:
                standard_type = StandardFormFieldType.SHORT_TEXT
            case FieldType.LEGAL:
                standard_type = StandardFormFieldType.MULTIPLE_CHOICE
                typeform_field.properties.choices = [
                    Choice(label="I accept"),
                    Choice(label="I don't accept"),
                ]
            case FieldType.YES_NO:
                standard_type = StandardFormFieldType.MULTIPLE_CHOICE
                typeform_field.properties.choices = [
                    Choice(label="Yes"),
                    Choice(label="No"),
                ]
            case FieldType.NPS:
                standard_type = StandardFormFieldType.OPINION_SCALE
            case FieldType.PICTURE_CHOICE:
                standard_type = StandardFormFieldType.MULTIPLE_CHOICE
            case _:
                standard_type = typeform_field.type
        return standard_type

    @staticmethod
    def _transform_validations(typeform_field_validations: Validation) -> StandardFieldValidations:
        return StandardFieldValidations(
            required=typeform_field_validations.required,
            max_length=typeform_field_validations.max_length,
            min_value=typeform_field_validations.min_value,
            max_value=typeform_field_validations.max_value
        )

    def _transform_properties(self, typeform_field_properties: FieldProperties) -> StandardFieldProperty:
        return StandardFieldProperty(
            description=typeform_field_properties.description,
            choices=[StandardChoice(
                ref=choice.ref,
                label=choice.label,
                attachment=self._transform_attachment(choice.attachment)
            ) for choice in typeform_field_properties.choices],
            fields=self._transform_fields(typeform_field_properties.fields),
            allow_multiple_selection=typeform_field_properties.allow_multiple_selection,
            allow_other_choice=typeform_field_properties.allow_other_choice,
            hide_marks=typeform_field_properties.hide_marks,
            button_text=typeform_field_properties.button_text,
            steps=typeform_field_properties.steps,
            rating_shape=typeform_field_properties.shape,
            labels=typeform_field_properties.labels,
            start_form=1 if typeform_field_properties.start_at_one else 0,
            date_format=self._format_typeform_date(typeform_field_properties.structure,
                                                   typeform_field_properties.separator)
        )

    # Transform date for typeform for eg YYYYMMDD's into YYYY/MM/DD format
    @staticmethod
    def _format_typeform_date(date_format: str, date_separator: str) -> str:
        if date_format and date_separator:
            combined_format = ""
            prev_char = None
            for char in date_format:
                # if the previous character is not None and is different from the current character
                if prev_char is not None and prev_char != char:
                    combined_format += date_separator
                combined_format += char
                prev_char = char
            return combined_format

    @staticmethod
    def _transform_form_settings(form: TypeFormDto):
        setting = StandardFormSettings()
        setting.provider = FormProvider.TYPEFORM
        setting.custom_url = form.id
        setting.embed_url = form.self.href
        setting.is_public = form.settings.is_public
        return setting

    def _transform_single_answer(self, answer: Answer) -> StandardFormResponseAnswer:
        standard_answer = StandardFormResponseAnswer(
            field=StandardAnswerField(
                id=answer.field.id,
                ref=answer.field.ref,
            ),
            type=answer.type,
            text=answer.text,
            choice=StandardChoiceAnswer(
                value=self._transform_choice_answer(answer),
                other=answer.choice.other
            ),
            choices=StandardChoicesAnswer(
                values=answer.choices.labels,
                other=answer.choices.other
            ),
            number=answer.number,
            boolean=answer.boolean,
            email=answer.email,
            date=answer.date,
            url=answer.url,
            file_url=answer.file_url,
            payment=StandardPaymentAnswer(
                amount=answer.payment.amount,
                last4=answer.payment.last4,
                name=answer.payment.name
            )
        )
        return standard_answer

    def _transform_answers(self, typeform_answers: List[Answer]) -> Dict[str, StandardFormResponseAnswer]:
        if typeform_answers is None:
            return {}
        standard_answers = {}
        for typeform_answer in typeform_answers:
            answer = self._transform_single_answer(typeform_answer)
            standard_answers[typeform_answer.field.id] = answer
        return standard_answers

    @staticmethod
    def _transform_choice_answer(answer: Answer):
        if answer.field.type == FieldType.YES_NO:
            return "Yes" if answer.boolean else "No"
        elif answer.field.type == FieldType.LEGAL:
            return "I accept" if answer.boolean else "I don't accept"
        else:
            return answer.choice.label
