import { PayloadAction, createSlice } from '@reduxjs/toolkit';

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
        setUpdateConsent: (state, action: PayloadAction<IConsentField>) => {
            const newConsentsWithoutUpdatedConsents = state.consents.filter((consent) => consent.id !== action.payload.id);
            return { ...state, consents: [...newConsentsWithoutUpdatedConsents, action.payload] };
        },
        setRemoveConsent: (state, action: PayloadAction<string>) => {
            const updatedConsents = state.consents.filter((consent) => consent.id !== action.payload);
            return { ...state, consents: [...updatedConsents] };
        },
        setPrivacyPoilicy: (state, action: PayloadAction<string>) => {
            return { ...state, privacy_policy: action.payload };
        }
    }
});

const reducerObj = { reducerPath: consent.name, reducer: consent.reducer };
export default reducerObj;
