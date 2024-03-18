import { JSONContent } from '@tiptap/react';

import { FormTheme } from '@app/constants/theme';

import { FormSlideLayout } from '../enums/form';

export interface StandardForm {
    formId: string;
    title: string;
    description?: string;
    buttonText?: string;
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
    fields: Array<FormField>;
    theme?: FormTheme;
}

export interface FormField {
    index: number;
    id: string;
    properties?: FormFieldProperties;
    validations?: FieldValidations;
    title?: JSONContent;
    description?: string;
    type?: FieldTypes;
    value?: string;
    imageUrl?: string;
}

interface FieldValidations {
    required?: boolean;
    maxLength?: number;
    minLength?: number;
    minValue?: number;
    mazValue?: number;
    regex?: number;
    minChoice?: number;
    maxChoices?: number;
}

interface FormFieldProperties {
    hidden?: boolean;
    fields?: Array<FormField>;
    placeholder?: string;
    choices?: Array<FieldChoice>;
    steps?: number;
    startFrom?: number;
    ratingShape?: string;
    dateFormat?: string;
    showQuestionNumbers?: boolean;
    allowMultipleSelection?: boolean;
    allowOtherOption?: boolean;
    layout?: FormSlideLayout;
    theme?: {
        title: string;
        primary: string;
        secondary: string;
        tertiary: string;
        accent: string;
    };
}

interface FieldChoice {
    id: string;
    value?: string;
    label?: string;
}

export enum FieldTypes {
    TEXT = 'text',
    SLIDE = 'slide',
    YES_NO = 'yes_no',
    LINK = 'url',
    DATE = 'date',
    PHONE_NUMBER = 'phone_number',
    EMAIL = 'email',
    NUMBER = 'number',
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
    NUMBER_INPUT = 'number_input',
    SHORT_TEXT_INPUT = 'short_text_input',
    LONG_TEXT_INPUT = 'long_text_input',
    MULTIPLE_CHOICE_INPUT = 'multiple_choice_input',
    RANKING_INPUT = 'ranking_input',
    RATING_INPUT = 'rating_input',
    DROP_DOWN_INPUT = 'drop_down_input',
    MEDIA_INPUT = 'media_input',
    MATRIX_ROW_INPUT = 'matrix_row_input'
}
