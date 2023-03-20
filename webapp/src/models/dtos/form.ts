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
    items: Array<any>;
    formId: string;
    title: string;
    description?: string | null | undefined;
    provider?: string;
    dataOwnerIdentifier?: string;
    settings?: {
        pinned: boolean;
        embedUrl?: string;
        customUrl: string;
        responseDataOwnerField?: string;
        private?: boolean;
        provider: string;
        roles?: Array<string>;
    };
    fields: Array<StandardFormQuestionDto>;
    createdTime?: string | Date;
    modifiedTime?: string | Date;
    responseId?: string;
    responseCreatedAt?: string;
    responseUpdatedAt?: string;
}

export interface StandardFormResponseDto {
    items: Array<any>;
    responseId: string;
    formId: string;
    formTitle: string;
    formCustomUrl: string;
    provider: string;

    deletionStatus?: string;
    requestForDeletion?: boolean;
    dataOwnerIdentifierType: string | null | undefined;
    dataOwnerIdentifier: string | null | undefined;
    responses: Array<{ questionId: string; answer: any }>;
    createdAt: string | Date;
    updatedAt: string | Date;
}
