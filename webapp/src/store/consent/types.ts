import { ConsentCategoryType, ConsentType, ResponseRetentionType } from '@app/models/enums/consentEnum';

export interface IConsentField {
    consentId: string;
    title?: string;
    description?: string;
    required?: boolean;
    type?: ConsentType;
    category?: ConsentCategoryType;
}

export interface IConsentState {
    formId: string;
    consents: IConsentField[];
    privacyPolicyUrl?: string;
    responseExpiration?: string;
    responseExpirationType: ResponseRetentionType;
}

export interface IConsentAnswer extends IConsentField {
    accepted?: boolean;
}

export interface ConsentAnswerDto extends IConsentAnswer {}