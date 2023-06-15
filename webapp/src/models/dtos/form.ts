import { UserDto } from '@app/models/dtos/UserDto';
import { UserStatus } from '@app/models/dtos/UserStatus';

import { ResponderGroupDto } from './groups';

export interface StandardFormQuestionDto {
    id?: string;
    questionId: string;
    formId?: string;

    properties?: any;

    attachment?: any;
    title: string;
    description?: string | null;
    type:
        | {
              type: string;
              options: Array<any>;
          }
        | any;
    required?: boolean | null | undefined;
    isMediaContent?: boolean;
    mediaContent?: boolean;
    isGroupQuestion?: boolean;
    groupQuestion?: any;
    answer?: any;
}

export interface StandardFormDto {
    items?: Array<any>;
    formId: string;
    title: string;
    description?: string | null | undefined;
    provider?: string;
    createdAt?: string | Date;
    dataOwnerIdentifier?: string;
    responses?: number;
    deletionRequests?: number;
    groups?: Array<ResponderGroupDto>;
    settings?: {
        pinned: boolean;
        embedUrl?: string;
        customUrl: string;
        responseDataOwnerField?: string;
        private?: boolean;
        provider: string;
        roles?: Array<string>;
    };
    importerDetails: UserStatus;
    fields: Array<StandardFormQuestionDto>;
    createdTime?: string | Date;
    modifiedTime?: string | Date;
    responseId?: string;
    responseCreatedAt?: string;
    responseUpdatedAt?: string;
}

export interface StandardFormResponseDto {
    answers: object;
    responseId: string;
    formId: string;
    formTitle: string;
    formCustomUrl: string;
    provider: string;
    createdAt: string | Date;
    updatedAt: string | Date;

    deletionStatus?: string;
    requestForDeletion?: boolean;
    dataOwnerIdentifier: string | null | undefined;
    responses: Array<{ questionId: string; answer: any }>;
}

export interface WorkspaceResponderDto {
    email: string;
    responses: number;
    deletionRequests: number;
}
