import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { PayloadAction, createSlice } from '@reduxjs/toolkit';

import environments from '@app/configs/environments';
import { ConsentCategoryType, ConsentType, ResponseRetentionType } from '@app/models/enums/consentEnum';

import { IConsentField, IConsentState } from './types';


const initialState: IConsentState = {
    formId: '',
    consents: [
        {
            consentId: 'consent_data_collection',
            title: 'Data Collection',
            description: 'We gather data from the responses you provide in our forms.',
            type: ConsentType.Checkbox,
            required: true,
            category: ConsentCategoryType.PurposeOfTheForm
        },
        {
            consentId: 'response_data_retention',
            title: 'Forever',
            type: ConsentType.Info,
            category: ConsentCategoryType.DataRetention
        }
    ],
    privacyPolicyUrl: environments.FORM_PRIVACY_POLICY_URL,
    responseExpiration: '',
    responseExpirationType: 'forever'
};
export const consent = createSlice({
    name: 'consent',
    initialState: initialState,
    reducers: {
        setFormConsent: (state, action) => {
            state.formId = action.payload.formId;
            state.consents = action.payload?.consent && action.payload?.consent?.length > 0 ? action.payload.consent : initialState.consents;
            state.responseExpiration = action.payload.settings.responseExpiration || initialState.responseExpiration;
            state.responseExpirationType = action.payload.settings.responseExpirationType || initialState.responseExpirationType;
            state.privacyPolicyUrl = action.payload.settings.privacyPolicyUrl || environments.FORM_PRIVACY_POLICY_URL;
        },
        setAddConsent: (state, action: PayloadAction<IConsentField>) => {
            return { ...state, consents: [...state.consents, action.payload] };
        },
        setResponderRights: (state) => {
            const consentField = {
                consentId: uuidv4(),
                type: ConsentType.Info,
                category: ConsentCategoryType.RespondersRights,
                title: 'Responder Rights'
            };
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
        setPrivacyPolicy: (state, action: PayloadAction<string>) => {
            return { ...state, privacyPolicyUrl: action.payload };
        },
        setResponseRetention: (
            state,
            action: PayloadAction<{
                expiration?: string;
                expirationType: ResponseRetentionType;
            }>
        ) => {
            return {
                ...state,
                responseExpiration: action.payload.expiration,
                responseExpirationType: action.payload.expirationType
            };
        },
        resetResponseRetention: (state) => {
            return { ...state, responseExpiration: '', responseExpirationType: 'forever' };
        },
        resetConsentState: () => {
            return { ...initialState };
        }
    }
});

const reducerObj = { reducerPath: consent.name, reducer: consent.reducer };
export default reducerObj;