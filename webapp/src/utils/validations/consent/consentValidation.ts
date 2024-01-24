import { ConsentType } from '@app/models/enums/consentEnum';
import { IConsentAnswer, IConsentField } from '@app/store/consent/types';

export const validateConsents = (consentAnswers: Record<string, IConsentAnswer>, consents: IConsentField[]) => {
    if (!consents) {
        return true;
    }
    const requiredConsentIds = consents?.filter((consent) => consent.required === true && consent.type === ConsentType.Checkbox).map((consent) => consent.consentId);
    const missingRequiredConsents = requiredConsentIds?.filter((consentId) => !consentAnswers[consentId]?.accepted);
    return missingRequiredConsents?.length === 0;
};