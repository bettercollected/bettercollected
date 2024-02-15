interface StandardForm {
    formId: string
    title: string
    description: string
    buttonText?: string
    version?: number;
    settings?: {
        pinned: boolean;
        embedUrl?: string;
        customUrl: string;
        responseDataOwnerField?: string;
        private?: boolean;
        provider: string;
        isPublished?: boolean;
        privacyPolicyUrl?: string;
        responseExpiration?: string;
        disableBranding: boolean;
        hidden: boolean;
        formCloseDate?: string;
        requireVerifiedIdentity?: boolean;
        showSubmissionNumber?: boolean;
    };
    fields: Array<FormField>
}

interface FormField {
    index: number
    id: string
    properties?: FormFieldProperties
    validations?: FieldValidations
    title?: string
    description?: string
    type?: any
    value?: string
}


interface FieldValidations {
    required?: boolean
    maxLength?: number
    minLength?: number
    minValue?: number
    mazValue?: number
    regex?: number
    minChoice?: number
    maxChoices?: number
}

interface FormFieldProperties {
    hidden?: boolean
    fields: Array<FieldChoice>
    placeholder?: string
    choices?: Array<any>
    steps?: number
    startFrom?: number
    ratingShape?: string
    dateFormat?: string
}

interface FieldChoice {
    id: string
    value?: string
    label?: string
}


enum FieldTypes {
    DATE = 'date',
    EMAIL = 'email',
    SHORT_TEXT = 'short_text',
    LONG_TEXT = 'long_text',
    MULTIPLE_CHOICE = 'multiple_choice',
    OPINION_SCALE = 'opinion_scale',
    RANKING = 'ranking',
    RATING = 'rating',
    DROP_DOWN = 'dropdown',
    MATRIX = 'matrix',
    FILE_UPLOAD = 'file_upload',
    GROUP = 'group',
    PAYMENT = 'payment',
    STATEMENT = 'statement',
    VIDEO_CONTENT = 'VIDEO_CONTENT',
    IMAGE_CONTENT = 'IMAGE_CONTENT',
    DATE_INPUT = 'date_input',
    EMAIL_INPUT = 'email_input',
    SHORT_TEXT_INPUT = 'short_text_input',
    LONG_TEXT_INPUT = 'long_text_input',
    MULTIPLE_CHOICE_INPUT = 'multiple_choice_input',
    RANKING_INPUT = 'ranking_input',
    RATING_INPUT = 'rating_input',
    DROP_DOWN_INPUT = 'drop_down_input',
    MEDIA_INPUT = 'media_input',
    MATRIX_ROW_INPUT = 'matrix_row_input'
}