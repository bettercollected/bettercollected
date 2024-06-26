import { JSONContent } from '@tiptap/react';

import { FormTheme } from '@app/constants/theme';
import { UserStatus } from '@app/models/dtos/UserStatus';
import { Parameters } from '@app/models/dtos/actions';
import { IConsentField } from '@app/store/consent/types';
import { IFormFieldValidation } from '@app/store/form-builder/types';

import { ResponseRetentionType } from '../enums/consentEnum';
import { FormSlideLayout } from '../enums/form';
import { FileMetadata } from '../types/fileTypes';
import { ResponderGroupDto } from './groups';

export interface StandardFormFieldProperties {
    hidden?: boolean;
    fields?: Array<StandardFormFieldDto>;
    placeholder?: string;
    choices?: Array<FieldChoice>;
    steps?: number;
    startFrom?: number;
    ratingShape?: string;
    dateFormat?: string;
    showQuestionNumbers?: boolean;
    allowMultipleSelection?: boolean;
    allowOtherChoice?: boolean;
    layout?: FormSlideLayout;
    theme?: {
        title: string;
        primary: string;
        secondary: string;
        tertiary: string;
        accent: string;
    };
    conditions?: any;
    mentions?: any;
    logicalOperator?: any;
    actions?: any;
}

export interface StandardFormFieldDto {
    id: string;
    questionId?: string;
    formId?: string;
    validations?: IFormFieldValidation;
    properties?: StandardFormFieldProperties;
    value?: string;
    attachment?: any;
    title?: string | JSONContent;
    description?: string | null;
    type:
        | {
              type: string;
              options: Array<any>;
          }
        | any;
    isMediaContent?: boolean;
    mediaContent?: boolean;
    isGroupQuestion?: boolean;
    groupQuestion?: any;
    answer?: any;
    index: number;
    imageUrl?: string;
}

export interface StandardFormDto {
    formId: string;
    importedFormId?: string;
    title: string;
    description?: string | null | undefined;
    buttonText?: string;
    version?: number;
    provider?: string;
    responses?: number;
    deletionRequests?: number;
    groups?: Array<ResponderGroupDto>;
    builderVersion?: string;
    isMultiPage?: boolean;
    welcomePage?: {
        title?: string;
        description?: string;
        layout?: FormSlideLayout;
        imageUrl?: string;
        buttonText?: string;
    };
    thankyouPage?: Array<{
        message?: string;
        buttonText?: string;
        buttonLink?: string;
        layout?: FormSlideLayout;
        imageUrl?: string;
    }>;
    settings?: {
        pinned: boolean;
        embedUrl?: string;
        customUrl: string;
        responseDataOwnerField?: string;
        private?: boolean;
        provider: string;
        isPublished?: boolean;
        roles?: Array<string>;
        privacyPolicyUrl?: string;
        responseExpiration?: string;
        responseExpirationType?: ResponseRetentionType;
        disableBranding: boolean;
        hidden: boolean;
        formCloseDate?: string;
        requireVerifiedIdentity?: boolean;
        showSubmissionNumber?: boolean;
        allowEditingResponse?: boolean;
        showOriginalForm?: boolean;
    };
    isPublished?: boolean;
    importerDetails?: UserStatus;
    consent?: Array<IConsentField>;
    fields: Array<StandardFormFieldDto>;
    createdTime?: string | Date;
    modifiedTime?: string | Date;
    coverImage?: string;
    logo?: string;
    createdAt?: string;
    updatedAt?: string;
    actions?: any;
    parameters?: Record<any, Array<Parameters>>;
    secrets?: Record<any, Array<Parameters>>;
    theme?: FormTheme;
    unauthorized?: boolean;
}

export interface StandardFormResponseDto {
    answers: {
        [fieldId: string]: AnswerDto;
    };
    responseId: string;
    formId?: string;
    formTitle?: string;
    formCustomUrl?: string;
    provider: string;
    createdAt: string | Date;
    updatedAt: string | Date;
    formImportedBy?: string;
    status?: string;
    requestForDeletion?: boolean;
    expiration?: string;
    expirationType?: ResponseRetentionType;
    dataOwnerIdentifier?: string | null | undefined;
    responses?: Array<{ questionId: string; answer: any }>;
}

export interface WorkspaceResponderDto {
    email: string;
    responses: number;
    deletionRequests: number;
}

export interface AnswerDto {
    field: {
        id: string;
    };
    type: string;
    text?: string;
    number?: number;
    email?: string;
    boolean?: boolean;
    date?: string;
    time?: string;
    url?: string;
    file_metadata?: FileMetadata;
    phoneNumber?: string;
    phone_number?: string;
    choice?: {
        id?: string;
        label?: string;
        value?: string;
    };
    choices?: {
        labels: Array<string>;
        values?: Array<string>;
        other?: string;
    };
}

interface AttachmentProperties {
    description?: string;
}

enum AttachmentType {
    IMAGE = 'image',
    VIDEO = 'video'
}

enum EmbedProvider {
    YOUTUBE = 'youtube',
    VIEMO = 'vimeo',
    NO_EMBED = 'no_embed'
}

export interface FieldChoice {
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
    LINEAR_RATING = 'linear_rating',
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
    MATRIX_ROW_INPUT = 'matrix_row_input',
    INPUT_FILE_UPLOAD = 'input_file_upload'
}

export const V2InputFields = [
    FieldTypes.DATE,
    FieldTypes.YES_NO,
    FieldTypes.MULTIPLE_CHOICE,
    FieldTypes.RATING,
    FieldTypes.LINEAR_RATING,
    FieldTypes.NUMBER,
    FieldTypes.SHORT_TEXT,
    FieldTypes.EMAIL,
    FieldTypes.PHONE_NUMBER,
    FieldTypes.DROP_DOWN,
    FieldTypes.MATRIX
];
