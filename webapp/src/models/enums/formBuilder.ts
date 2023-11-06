export enum KeyType {
    Escape = 'Escape',
    ArrowDown = 'ArrowDown',
    ArrowUp = 'ArrowUp',
    Backspace = 'Backspace',
    Command = '/',
    CommandKey = 'CommandKey',
    Enter = 'Enter',
    Shift = 'Shift',
    Tab = 'Tab',
    ShiftTab = 'Shift + Tab'
}

export enum BlockTypes {
    INPUT_BLOCKS = 'Elements',
    LAYOUT_BLOCKS = 'Layout Blocks',
    QUESTION_INPUT_BLOCKS = 'Elements with Label',
    CONDITIONAL = 'Conditional'
}

export enum FormBuilderTagNames {
    LAYOUT_HEADER1 = 'h1',
    LAYOUT_HEADER2 = 'h2',
    LAYOUT_HEADER3 = 'h3',
    LAYOUT_HEADER4 = 'h4',
    LAYOUT_SHORT_TEXT = 'p',
    LAYOUT_LABEL = 'strong',
    LAYOUT_DIVIDER = 'divider',
    LAYOUT_MARKDOWN = 'markdown',

    INPUT_SHORT_TEXT = 'input_short_text',
    INPUT_LONG_TEXT = 'input_long_text',
    INPUT_MULTIPLE_CHOICE = 'input_multiple_choice',
    INPUT_MULTISELECT = 'input_multiselect',
    INPUT_CHECKBOXES = 'input_checkboxes',
    INPUT_EMAIL = 'input_email',
    INPUT_NUMBER = 'input_number',
    INPUT_PHONE_NUMBER = 'input_phone_number',
    INPUT_LINK = 'input_link',
    INPUT_DATE = 'input_date',
    INPUT_TIME = 'input_time',
    INPUT_DATE_RANGE = 'input_date_range',
    INPUT_TIME_RANGE = 'input_time_range',
    INPUT_DATETIME_RANGE = 'input_datetime_range',
    INPUT_DROPDOWN = 'input_dropdown',
    INPUT_RATING = 'input_rating',
    INPUT_LINEAR_SCALE = 'input_linear_scale',
    INPUT_TEMPLATE_BUTTON = 'input_template_button',
    INPUT_FILE_UPLOAD = 'input_file_upload',
    INPUT_RANKING = 'input_ranking',
    INPUT_MATRIX = 'input_matrix',
    INPUT_MEDIA = 'input_file_upload',

    CONDITIONAL = 'conditional',

    EMBED_IMAGE = 'embed_image',
    EMBED_VIDEO = 'embed_video',
    EMBED_AUDIO = 'embed_audio',
    EMBED_ANYTHING = 'embed_anything',
    EMBED_CODE = 'embed_code',
    EMBED_RECAPTCHA = 'embed_recaptcha',

    QUESTION_SHORT_TEXT = 'question_short_text',
    QUESTION_LONG_TEXT = 'question_long_text',
    QUESTION_MULTIPLE_CHOICE = 'question_multiple_choice',
    QUESTION_CHECKBOXES = 'question_checkboxes',
    QUESTION_EMAIL = 'question_email',
    QUESTION_NUMBER = 'question_number',
    QUESTION_PHONE_NUMBER = 'question_phone_number',
    QUESTION_LINK = 'question_link',
    QUESTION_DATE = 'question_date',
    QUESTION_TIME = 'question_time',
    QUESTION_DATE_RANGE = 'question_date_range',
    QUESTION_TIME_RANGE = 'question_time_range',
    QUESTION_DATETIME_RANGE = 'question_datetime_range',
    QUESTION_DROPDOWN = 'question_dropdown',
    QUESTION_MULTISELECT = 'question_multiselect',
    QUESTION_RANKING = 'question_ranking',
    QUESTION_RATING = 'question_rating',
    QUESTION_LINEAR_SCALE = 'question_linear_scale',
    QUESTION_FILE_UPLOAD = 'question_file_upload',
    QUESTION_INPUT_MATRIX = 'question_matrix',
    QUESTION_INPUT_MEDIA = 'question_file_upload'
}

export function getFormBuilderTagNameFromString(value: string) {
    return value as FormBuilderTagNames;
}

export const NonInputFormBuilderTagNames = [
    FormBuilderTagNames.LAYOUT_HEADER1,
    FormBuilderTagNames.LAYOUT_HEADER2,
    FormBuilderTagNames.LAYOUT_HEADER3,
    FormBuilderTagNames.LAYOUT_HEADER4,
    FormBuilderTagNames.LAYOUT_SHORT_TEXT,
    FormBuilderTagNames.LAYOUT_LABEL,
    FormBuilderTagNames.LAYOUT_DIVIDER,
    FormBuilderTagNames.EMBED_IMAGE,
    FormBuilderTagNames.EMBED_VIDEO,
    FormBuilderTagNames.EMBED_AUDIO,
    FormBuilderTagNames.EMBED_ANYTHING,
    FormBuilderTagNames.EMBED_CODE,
    FormBuilderTagNames.EMBED_RECAPTCHA,
    FormBuilderTagNames.CONDITIONAL
];
