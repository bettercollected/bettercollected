from typing import List, Dict, Any
import re
import json

FieldTypes = {
    'TEXT': 'text',
    'IMAGE_CONTENT': 'image_content',
    'VIDEO_CONTENT': 'video_content',
    'MATRIX': 'matrix',
    'LINEAR_RATING': 'linear_rating',
    'RATING': 'rating',
    'NUMBER': 'number',
    'SHORT_TEXT': 'short_text',
    'LONG_TEXT': 'long_text',
    'LINK': 'url',
    'EMAIL': 'email',
    'DATE': 'date',
    'YES_NO': 'yes_no',
    'MULTIPLE_CHOICE': 'multiple_choice',
    'DROP_DOWN': 'dropdown',
    'PHONE_NUMBER': 'phone_number',
    'FILE_UPLOAD': 'file_upload'
}

FormBuilderTagNames = {
    'INPUT_RATING': 'input_rating',
    'INPUT_NUMBER': 'input_number',
    'INPUT_SHORT_TEXT': 'input_short_text',
    'INPUT_LONG_TEXT': 'input_long_text',
    'INPUT_LINK': 'input_link',
    'INPUT_EMAIL': 'input_email',
    'INPUT_DATE': 'input_date',
    'INPUT_MULTIPLE_CHOICE': 'input_multiple_choice',
    'INPUT_DROPDOWN': 'input_dropdown',
    'INPUT_CHECKBOXES': 'input_checkboxes',
    'INPUT_PHONE_NUMBER': 'input_phone_number',
    'INPUT_RANKING': 'input_ranking',
    'INPUT_FILE_UPLOAD': 'input_file_upload'
}


def return_string_form_tip_tap_json(title: dict | str):
    def extract_texts(content):
        if isinstance(content, list):
            text = ''
            for item in content:
                text += extract_texts(item) + ' '
            return text
        elif isinstance(content, dict):
            text = ''
            for key, value in content.items():
                if key =="text":
                    text += value
                if key == "content":
                    text += extract_texts(value)
            return text
        elif isinstance(content, str):
            return content
        return ''
    return extract_texts(title)

IgnoredResponsesFieldType = [FieldTypes['TEXT'], None, FieldTypes['IMAGE_CONTENT'], FieldTypes['VIDEO_CONTENT']]

def extract_text_from_json(field, is_row = False) -> str:
    if field.get("title") is not None and field.get("title") != "":
        return return_string_form_tip_tap_json(field.get("title"))
    if is_row:
        return "Row " + str(field.get("index") + 1)
    return get_placeholder_value_for_title(field.get("type"))

def get_fields_from_v2_form(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    fields = []
    for slide in form.get('fields', []):
        filtered_fields = [
            field for field in slide.get('properties', {}).get('fields', [])
            if field['type'] not in IgnoredResponsesFieldType
        ]
        for field in filtered_fields:
            field["title"] = extract_text_from_json(field)
            if field['type'] != FieldTypes['MATRIX']:
                fields.append(field)
            else:
                matrix_rows = [
                    {**row, 'title': f"{extract_text_from_json(field)}[{extract_text_from_json(row, True)}]"}
                    for index,row in enumerate(field.get('properties', {}).get('fields', []))
                ]
                fields.extend(matrix_rows)
    return [field for field in fields if field is not None]

def get_answer_for_field(response: Dict[str, Any], field: Dict[str, Any]) -> Any:

    answer = response.get('answers', {}).get(field['id'],{})
    if field['type'] in [FormBuilderTagNames['INPUT_RATING'], FormBuilderTagNames['INPUT_NUMBER'],
                         FieldTypes['LINEAR_RATING'], FieldTypes['RATING'], FieldTypes['NUMBER']]:
        return answer.get('number')
    if field['type'] in [FieldTypes['SHORT_TEXT'], FieldTypes["TEXT"], FieldTypes['LONG_TEXT'],
                         FormBuilderTagNames['INPUT_SHORT_TEXT'], FormBuilderTagNames['INPUT_LONG_TEXT']]:
        return answer.get('text')
    if field['type'] in [FieldTypes['LINK'], FormBuilderTagNames['INPUT_LINK']]:
        return answer.get('url')
    if field['type'] in [FieldTypes['EMAIL'], FormBuilderTagNames['INPUT_EMAIL']]:
        return answer.get('email')
    if field['type'] in [FieldTypes['DATE'], FormBuilderTagNames['INPUT_DATE']]:
        return answer.get('date')
    if field['type'] == FieldTypes['YES_NO']:
        return 'Yes' if answer.get('boolean') else 'No' if answer.get('boolean') is False else ''
    if field['type'] in [FieldTypes['MULTIPLE_CHOICE'], FieldTypes['DROP_DOWN']]:
        return get_choices_value(field, answer)
    if field['type'] in [FormBuilderTagNames['INPUT_MULTIPLE_CHOICE'], FormBuilderTagNames['INPUT_DROPDOWN']]:
        return next((choice['value'] for choice in field.get('properties', {}).get('choices', []) if choice['id'] == answer.get('choice', {}).get('value')), None)
    if field['type'] == FormBuilderTagNames['INPUT_CHECKBOXES']:
        choices_answers = answer.get('choices', {}).get('values')
        compare_ids = isinstance(choices_answers, list) and all(re.match('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', choice) for choice in choices_answers)
        if not compare_ids:
            choices = [choice for choice in field.get('properties', {}).get('choices', []) if choice['value'] in answer.get('choices', {}).get('values', [])]
            return ', '.join(choice['value'] for choice in choices)
        choices = [choice for choice in field.get('properties', {}).get('choices', []) if choice['id'] in answer.get('choices', {}).get('values', [])]
        return ', '.join(choice['value'] for choice in choices)
    if field['type'] in [FieldTypes['PHONE_NUMBER'], FormBuilderTagNames['INPUT_PHONE_NUMBER']]:
        return answer.get('phone_number')
    if field['type'] == FormBuilderTagNames['INPUT_RANKING']:
        return ', '.join(choice['value'] for choice in answer.get('choices', {}).get('values', []))
    if field['type'] in [FormBuilderTagNames['INPUT_FILE_UPLOAD'], FieldTypes['FILE_UPLOAD']]:
        return answer.get('file_metadata', {}).get('name')
    return ''

def get_choices_value(field: Dict[str, Any], answer: Dict[str, Any]) -> str:
    choices = field.get('properties', {}).get('choices', [])
    if field.get('properties', {}).get('allow_multiple_selection'):
        selected_choices = [choice for choice in choices if choice['id'] in answer.get('choices', {}).get('values', [])]
    else:
        selected_choices = [choice for choice in choices if choice['id'] == answer.get('choice', {}).get('value')]
    
    other_value = get_multiple_choice_other_value(answer, field.get('properties', {}).get('allow_multiple_selection', False))
    choices_value = [choice['value'] if 'value' in choice and choice["value"] else f"Item {choices.index(choice) + 1}" for choice in selected_choices]
    
    if other_value:
        return ', '.join(choices_value + [other_value])
    return ', '.join(choices_value)

def get_multiple_choice_other_value(answer: Dict[str, Any], multiple_selection: bool = False) -> str:
    if multiple_selection:
        return answer.get('choices', {}).get('other', '')
    return answer.get('choice', {}).get('other', '')


def get_placeholder_value_for_title(field_type):
    placeholders = {
        'email': 'Enter Your Email Address',
        'number': 'Enter Number',
        'short_text': 'Enter Question',
        'link': 'Enter Link',
        "url": "Enter Link",
        'phone_number': 'Enter Your Phone Number',
        'file_upload': 'Upload Your File',
        'yes_no': 'Are you sure?',
        'dropdown': 'Select an option',
        'multiple_choice': 'Select from list below.',
        'text': 'Add Text',
        'rating': 'Rate from 1 to 5',
        'date': 'Select a date',
        'linear_rating': 'Rate from 1 to 10',
        'matrix': 'Matrix Field'
    }
    return placeholders.get(field_type, 'No Field Selected')


def get_questions_and_answers(form: Dict[str, Any], response: Dict[str, Any]) -> List[Dict[str, Any]]:
    fields = get_fields_from_v2_form(form)
    return [
        {
            'field_id': field['id'],
            'title': field['title'],
            'answer': get_answer_for_field(response, field)
        }
        for field in fields
    ]