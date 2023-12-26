import { UserStatus } from '@app/models/dtos/UserStatus';
import { Parameters } from '@app/models/dtos/actions';
import { IConsentField } from '@app/store/consent/types';
import { IFormFieldValidation } from '@app/store/form-builder/types';

import { ResponseRetentionType } from '../enums/consentEnum';
import { FileMetadata } from '../types/fileTypes';
import { ResponderGroupDto } from './groups';

export interface StandardFormFieldDto {
    id: string;
    questionId?: string;
    formId?: string;
    validations?: IFormFieldValidation;
    properties?: any;
    value?: string;
    attachment?: any;
    title: string;
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
}

export interface StandardFormDto {
    formId: string;
    title: string;
    description?: string | null | undefined;
    buttonText?: string;
    version?: number;
    provider?: string;
    responses?: number;
    deletionRequests?: number;
    groups: Array<ResponderGroupDto>;
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
    };
    isPublished?: boolean;
    importerDetails?: UserStatus;
    consent: Array<IConsentField>;
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
