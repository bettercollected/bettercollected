import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { PayloadAction, createSlice } from '@reduxjs/toolkit';

import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';

import { IConsentField, IConsentState } from './types';

const initialState: IConsentState = {
    form_id: '',
    consents: []
};
export const consent = createSlice({
    name: 'consent',
    initialState: initialState,
    reducers: {
        setAddConsent: (state, action: PayloadAction<IConsentField>) => {
            return { ...state, consents: [...state.consents, action.payload] };
        },

        setResponderRights: (state) => {
            const consentField = { consentId: uuidv4(), type: ConsentType.Info, category: ConsentCategoryType.RespondersRights };
            const newConsentsWithoutUpdatedResponderRights = state.consents.filter((consent) => consent.category !== ConsentCategoryType.RespondersRights);
            return { ...state, consents: [...newConsentsWithoutUpdatedResponderRights, consentField] };
        },
        setUpdateConsent: (state, action: PayloadAction<IConsentField>) => {
            const newConsentsWithoutUpdatedConsents = state.consents.filter((consent) => consent.consentId !== action.payload.consentId);
            return { ...state, consents: [...newConsentsWithoutUpdatedConsents, action.payload] };
        },
        setRemoveConsent: (state, action: PayloadAction<string>) => {
            const updatedConsents = state.consents.filter((consent) => consent.consentId !== action.payload);
            return { ...state, consents: [...updatedConsents] };
        },
        setPrivacyPoilicy: (state, action: PayloadAction<string>) => {
            return { ...state, privacy_policy: action.payload };
        },
        resetConsentState: () => {
            return { ...initialState };
        }
    }
});

const reducerObj = { reducerPath: consent.name, reducer: consent.reducer };
export default reducerObj;
