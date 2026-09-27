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
            # Internal ("for office use only") fields belong to the
            # organisation: never in respondent copies, webhooks or chat posts.
            and not field.get('internal')
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
        'matrix': 'Matrix Field',
        'tabular_input': 'Tabular Input Field'
    }
    return placeholders.get(field_type, 'No Field Selected')


# ---------------------------------------------------------------------------
# Repeating groups
#
# A repeating group is a ``group`` field with ``properties.repeat``; its
# answer is ``{"type": "group", "items": [{<child id>: <answer>}, ...]}``.
# Exports follow one rule (same as the webapp CSV export,
# ``webapp/src/utils/repeating-groups.ts``): groups of at most
# ``REPEAT_COLUMNS_EXPORT_MAX`` items become columns per item
# ("Applicant 1 – Name"), larger ones a separate table with one row per item,
# unless the creator chose ``export_layout`` explicitly.
# ---------------------------------------------------------------------------

REPEAT_COLUMNS_EXPORT_MAX = 5
GROUP_TYPE = 'group'
RESPONSE_ID_COLUMN = 'Response ID'


def _get(mapping: Dict[str, Any], snake: str, camel: str, default=None):
    if not isinstance(mapping, dict):
        return default
    value = mapping.get(snake, mapping.get(camel))
    return default if value is None else value


def get_repeat_settings(field: Dict[str, Any]) -> Dict[str, Any] | None:
    """Normalised repeat settings of a repeating group field, else None."""
    if field.get('type') != GROUP_TYPE:
        return None
    repeat = (field.get('properties') or {}).get('repeat')
    if not isinstance(repeat, dict):
        return None
    max_items = int(_get(repeat, 'max_items', 'maxItems', 3))
    layout = _get(repeat, 'export_layout', 'exportLayout')
    if layout not in ('columns', 'rows'):
        layout = 'columns' if max_items <= REPEAT_COLUMNS_EXPORT_MAX else 'rows'
    return {
        'min_items': int(_get(repeat, 'min_items', 'minItems', 1)),
        'max_items': max_items,
        'item_label': _get(repeat, 'item_label', 'itemLabel', 'Item'),
        'export_layout': layout,
    }


def get_group_children(field: Dict[str, Any]) -> List[Dict[str, Any]]:
    children = (field.get('properties') or {}).get('fields') or []
    return [
        {**child, 'title': extract_text_from_json(child)}
        for child in children
        if child.get('type') not in IgnoredResponsesFieldType
    ]


def get_group_items(response: Dict[str, Any], field: Dict[str, Any]) -> List[Dict[str, Any]]:
    answer = (response.get('answers') or {}).get(field['id']) or {}
    items = answer.get('items') if isinstance(answer, dict) else None
    return [item if isinstance(item, dict) else {} for item in items] if isinstance(items, list) else []


def _item_answer(item: Dict[str, Any], child: Dict[str, Any]):
    answer = get_answer_for_field({'answers': item}, child)
    return '' if answer is None else answer


def get_questions_and_answers(
    form: Dict[str, Any], response: Dict[str, Any], fixed_columns: bool = False
) -> List[Dict[str, Any]]:
    """Question/answer pairs of a response.

    Repeating groups expand per item ("Applicant 2 – Name"). With
    ``fixed_columns`` (spreadsheets) the column set does not depend on the
    response: columns-layout groups expand to their maximum, rows-layout groups
    contribute only their item count (the items go to ``get_group_tables``),
    and a trailing Response ID column links the two.
    """
    entries: List[Dict[str, Any]] = []
    has_row_tables = False
    for field in get_fields_from_v2_form(form):
        repeat = get_repeat_settings(field)
        if repeat is None:
            entries.append({
                'field_id': field['id'],
                'title': field['title'],
                'answer': get_answer_for_field(response, field)
            })
            continue
        items = get_group_items(response, field)
        if fixed_columns and repeat['export_layout'] == 'rows':
            has_row_tables = True
            entries.append({
                'field_id': field['id'],
                'title': f"{field['title']} ({repeat['item_label']} count)",
                'answer': len(items),
            })
            continue
        count = repeat['max_items'] if fixed_columns else len(items)
        children = get_group_children(field)
        for position in range(count):
            item = items[position] if position < len(items) else {}
            for child in children:
                entries.append({
                    'field_id': f"{field['id']}.{position}.{child['id']}",
                    'title': f"{repeat['item_label']} {position + 1} – {child['title']}",
                    'answer': _item_answer(item, child),
                })
    if fixed_columns and has_row_tables:
        entries.append({'field_id': 'response_id', 'title': RESPONSE_ID_COLUMN, 'answer': response.get('response_id', '')})
    return entries


def get_group_tables(form: Dict[str, Any], response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One table per rows-layout group: header + one row per item, keyed by
    the response id and the item number."""
    tables = []
    for field in get_fields_from_v2_form(form):
        repeat = get_repeat_settings(field)
        if repeat is None or repeat['export_layout'] != 'rows':
            continue
        children = get_group_children(field)
        rows = [
            [response.get('response_id', ''), position + 1] + [_item_answer(item, child) for child in children]
            for position, item in enumerate(get_group_items(response, field))
        ]
        tables.append({
            'field_id': field['id'],
            'title': field['title'],
            'headers': [RESPONSE_ID_COLUMN, repeat['item_label']] + [child['title'] for child in children],
            'rows': rows,
        })
    return tables


def sheet_title_for(title: str) -> str:
    """A valid, stable Google Sheets tab name for a group table."""
    cleaned = re.sub(r"[\[\]:*?/\\']", ' ', str(title or 'Group')).strip() or 'Group'
    return cleaned[:95]


def column_letter(count: int) -> str:
    """Spreadsheet column name of the ``count``-th column (1 → A, 27 → AA)."""
    count = max(1, int(count))
    letters = ''
    while count:
        count, remainder = divmod(count - 1, 26)
        letters = chr(ord('A') + remainder) + letters
    return letters
