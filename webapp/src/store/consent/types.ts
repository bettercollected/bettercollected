import { ConsentCategoryType, ConsentType, RetentionType } from '@app/models/enums/consentEnum';

export interface IConsentField {
    consentId: string;
    title?: string;
    description?: string;
    required?: boolean;
    type?: ConsentType;
    category?: ConsentCategoryType;
    expirationDate?: string;
    retentionType?: RetentionType;
}

export interface IConsentState {
    form_id: string;
    consents: IConsentField[];
    privacy_policy?: string;
}

export interface IConsentAnswer extends IConsentField {
    accepted?: boolean;
}

export interface ConsentAnswerDto extends IConsentAnswer {}
