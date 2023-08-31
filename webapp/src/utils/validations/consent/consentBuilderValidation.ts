import { IConsentState } from '@app/store/consent/types';

export const validateConsentBuilder = (consent: IConsentState) => {
    if (!consent.privacy_policy || typeof consent.privacy_policy !== 'string') {
        return false;
    }
    return true;
};
