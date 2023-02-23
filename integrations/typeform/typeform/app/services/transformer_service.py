from typing import Any, Dict, List

from fastapi import HTTPException

from common.enums.form_provider import FormProvider
from common.models.standard_form import (
    StandardFormDto,
    StandardFormQuestionDto,
    StandardFormResponseAnswerDto,
    StandardFormResponseDto,
    StandardFormSettingDto, StandardAttachment, StandardProperties, EmbedProvider
)
from common.services.transformer_service import FormTransformerService
from typeform.app.models.typeform_models import \
    TypeFormTransformerDto, TypeFormField, Choice, FieldType, Answer, ResponseType, \
    Attachment, TypeFormResponse, TypeFormDto


class TypeFormTransformerService(FormTransformerService):
    def transform_forms(self, forms: List[Dict[str, Any]]) -> List[StandardFormDto]:
        standard_forms = [self.transform_basic_form(form) for form in forms]
        return standard_forms

    # TODO : Remove Dict and use concrete type that is specific to typeform
    # Transformer for basic form that is initially returned from typeform without details
    def transform_basic_form(self, form: Dict[str, Any]) -> StandardFormDto:
        try:
            typeform_dto = TypeFormTransformerDto(**form)
            standard_form = StandardFormDto()
            standard_form.formId = typeform_dto.formId
            standard_form.title = typeform_dto.info.title
            standard_form.settings = self._transform_form_settings(typeform_dto)
            return standard_form
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Data transformation failed. {error}")

    # TODO : Remove Dict and use concrete type that is specific to typeform
    def transform_single_form(self, form: Dict[str, Any]) -> StandardFormDto:
        try:
            typeform = TypeFormDto(**form)
            standard_form = StandardFormDto()
            standard_form.formId = typeform.id
            standard_form.title = typeform.title
            standard_form.questions = self._transform_questions(typeform.fields)
            standard_form.settings = self._transform_form_settings(typeform) if typeform.settings else None
            return standard_form
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Data transformation failed. {error}")

    def transform_form_responses(self, responses: List[Dict[str, Any]]) -> List[StandardFormResponseDto]:
        standard_form_responses = [self.transform_single_form_response(response) for response in responses]
        return standard_form_responses

    def transform_single_form_response(self,
                                       response: Dict[str, Any]) -> StandardFormResponseDto:
        try:
            response = TypeFormResponse(**response)
            standard_form_response = StandardFormResponseDto()
            standard_form_response.responseId = response.response_id
            standard_form_response.provider = FormProvider.TYPEFORM
            standard_form_response.createdAt = response.landed_at
            standard_form_response.updatedAt = response.submitted_at
            standard_form_response.responses = self._transform_answers(response.answers)
            return standard_form_response
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Data transformation failed. {error}")

    def _transform_questions(self, questions: List[TypeFormField]) -> List[StandardFormQuestionDto]:
        transformed_questions = list(map(self._transform_single_question, questions))
        return transformed_questions

    def _transform_attachment(self, attachment: Attachment) -> StandardAttachment:
        std_attachment = StandardAttachment()
        std_attachment.type = attachment.type
        std_attachment.href = attachment.href
        std_attachment.properties = StandardProperties(description=attachment.properties.description)
        if EmbedProvider.YOUTUBE in attachment.href:
            std_attachment.embed_provider = EmbedProvider.YOUTUBE
        elif EmbedProvider.VIEMO in attachment.href:
            std_attachment.embed_provider = EmbedProvider.VIEMO
        else:
            std_attachment.embed_provider = EmbedProvider.NO_EMBED
        return std_attachment

    def _transform_single_question(self, item: TypeFormField) -> StandardFormQuestionDto:
        question = StandardFormQuestionDto()
        question.questionId = item.id
        question.title = item.title
        question.description = item.properties.description if item.properties and item.properties.description else None
        question.type = {}
        question.required = item.validations.required if item.validations else None
        question.attachment = self._transform_attachment(item.attachment) if item.attachment else None
        item_properties = item.properties
        # TODO: Refactor all this as properties instead of type.type which is really bad
        # TODO Make standard types also not in string only
        match item.type:
            case FieldType.MATRIX:
                questions = []
                for field in item_properties.fields:
                    ques = {'questionId': field.id, 'rowQuestion': {
                        "title": field.title
                    }}
                    questions.append(ques)
                    choices = [{"value": choice.label} for choice in field.properties.choices]
                    grid = {
                        "columns": {
                            "type": "CHECKBOX" if field.properties.allow_multiple_selection else "RADIO",
                            "options": choices
                        }
                    }
                    question.type['grid'] = grid
                question.type['questions'] = questions
                question.isGroupQuestion = True
            case FieldType.RANKING:
                question.type['type'] = "RANKING"
                question.type['options'] = self._transform_choices(item_properties.choices)
            case FieldType.SHORT_TEXT:
                question.type['type'] = 'INPUT_FIELD'
            case FieldType.LONG_TEXT:
                question.type['paragraph'] = True
            case FieldType.MULTIPLE_CHOICE:
                if item.properties.allow_multiple_selection:
                    question.type['type'] = "CHECKBOX"
                else:
                    question.type['type'] = "RADIO"
                question.type['options'] = self._transform_choices(item_properties.choices)
            case FieldType.YES_NO:
                question.type['type'] = "RADIO"
                question.type['options'] = [{'value': 'Yes'}, {'value': 'No'}]
            case FieldType.DROPDOWN:
                question.type['type'] = "DROP_DOWN"
                question.type['options'] = self._transform_choices(item_properties.choices)
            case FieldType.FILE_UPLOAD:
                question.type['folderId'] = item.id
            # TODO: Refactor this low high to pass field type also not only low high
            case FieldType.OPINION_SCALE:
                question.type['low'] = 1 if item_properties.start_at_one else 0
                question.type['high'] = item_properties.steps
            case FieldType.DATE:
                question.type['type'] = "DATE"
                question.type['date_format'] = self._format_typeform_date(item_properties.structure,
                                                                          item_properties.separator)
            case FieldType.RATING:
                question.type['type'] = "RATING"
                question.type['shape'] = item_properties.shape
                question.type['steps'] = item_properties.steps
            case FieldType.ADDRESS:
                question.type['type'] = "GROUP"
                question.isGroupQuestion = True
                question.type['questions'] = self._transform_questions(item.properties.fields)
            case FieldType.CONTACT_INFO:
                question.type['type'] = "GROUP"
                question.isGroupQuestion = True
                question.type['questions'] = self._transform_questions(item.properties.fields)
            case FieldType.GROUP:
                question.type['type'] = "GROUP"
                question.isGroupQuestion = True
                question.type['questions'] = self._transform_questions(item_properties.fields)
                question.answer = [{'questionId': q.id, 'answer': ''} for q in item_properties.fields]
            case FieldType.STATEMENT:
                question.type['type'] = "STATEMENT"
            # TODO: Refactor this to include type not only low high i.e could be generic like linear scale
            case FieldType.NPS:
                question.type['low'] = 0
                question.type['high'] = item_properties.steps
            case FieldType.PICTURE_CHOICE:
                if item.properties.allow_multiple_selection:
                    question.type['type'] = "CHECKBOX"
                else:
                    question.type['type'] = "RADIO"
                question.type['options'] = self._transform_choices(item_properties.choices)
            case _:
                question.type['type'] = "INPUT_FIELD"
                question.type['data'] = item.dict()
        return question

    def _format_typeform_date(self, date_format: str, date_separator: str) -> str:
        combined_format = ""
        prev_char = None
        for char in date_format:
            # if the previous character is not None and is different from the current character
            if prev_char is not None and prev_char != char:
                combined_format += date_separator
            combined_format += char
            prev_char = char
        return combined_format

    def _transform_choices(self, choices: List[Choice]) -> List[Dict]:
        return [{'value': choice.label, 'attachment': choice.attachment} for choice in choices]

    def _transform_form_settings(self, form: TypeFormDto):
        setting = StandardFormSettingDto()
        setting.provider = FormProvider.TYPEFORM
        setting.customUrl = form.id
        setting.embedUrl = form.self.href
        setting.private = not form.settings.is_public
        return setting

    def _transform_single_answer(self, answer: Answer) -> Dict[str, StandardFormResponseAnswerDto]:
        question_id = answer.field.id
        standard_answer = StandardFormResponseAnswerDto()
        standard_answer.questionId = question_id
        match answer.type:
            case ResponseType.TEXT:
                # TODO: Refactor this in frontend and standarized both google and typeform in one
                if answer.field.type == FieldType.DROPDOWN:
                    standard_answer.answer = [answer.text]
                else:
                    standard_answer.answer = answer.text
            case ResponseType.CHOICE:
                standard_answer.answer = [
                    {"value": answer.choice.label} if answer.choice.label else answer.choice.other]
            case ResponseType.CHOICES:
                standard_answer.answer = []
                if answer.choices.labels:
                    standard_answer.answer.extend([{"value": label} for label in answer.choices.labels])
                if answer.choices.other:
                    standard_answer.answer.append(answer.choices.other)
            case ResponseType.NUMBER:
                # TODO: Refactor this to make standard in frontend since this is only one value
                # not need to pass it as array but frontend expects it
                if answer.field.type == FieldType.OPINION_SCALE or answer.field.type == FieldType.NPS:
                    standard_answer.answer = [answer.number]
                else:
                    standard_answer.answer = answer.number
            case ResponseType.BOOLEAN:
                if answer.field.type == FieldType.YES_NO:
                    standard_answer.answer = 'Yes' if answer.boolean else 'No'
                else:
                    standard_answer.answer = answer.boolean
            case ResponseType.EMAIL:
                standard_answer.answer = answer.email
            case ResponseType.DATE:
                standard_answer.answer = answer.date
            case ResponseType.URL:
                standard_answer.answer = answer.url
            case ResponseType.FILE_URL:
                standard_answer.answer = answer.file_url
            case ResponseType.PAYMENT:
                standard_answer.answer = answer.payment.dict()
            case ResponseType.PHONE_NUMBER:
                standard_answer.answer = answer.phone_number
        return {question_id: standard_answer}

    def _transform_answers(self, answers: List[Answer]) \
            -> Dict[str, StandardFormResponseDto]:
        if answers is None:
            return {}
        standard_answers = {}
        for answer in answers:
            answer = self._transform_single_answer(answer)
            if type(answer) is list:
                for a in answer:
                    standard_answers = {**standard_answers, **a}
            else:
                standard_answers = {**standard_answers, **answer}
        return standard_answers
