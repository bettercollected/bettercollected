import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';

export interface IConsentField {
    id: string;
    title?: string;
    description?: string;
    required?: boolean;
    type?: ConsentType;
    category?: ConsentCategoryType;
}

export interface IConsentState {
    form_id: string;
    consents: IConsentField[];
    privacy_policy?: string;
}
