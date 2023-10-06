import { IConsentState } from '@app/store/consent/types';

export const validateConsentBuilder = (consent: IConsentState) => {
    return !!consent.privacyPolicyUrl;
};
