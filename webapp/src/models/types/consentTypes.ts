import { IConsentField } from '@app/store/consent/types';

export interface IConsentOption extends Omit<IConsentField, 'consentId'> {
    consentId?: string;
    isRecentlyAdded?: boolean;
}
