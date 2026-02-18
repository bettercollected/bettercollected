import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { RootState } from '@app/store/store';

import { IConsentAnswer } from '../consent/types';

interface FillIBuilderState {
    consentAnswers: {
        [consentId: string]: IConsentAnswer;
    };
    anonymize?: boolean;
}

const initialState: FillIBuilderState = {
    consentAnswers: {},
    anonymize: false
};

const slice = createSlice({
    name: 'fillForm',
    initialState: initialState,
    reducers: {
        resetFillForm: () => {
            return initialState;
        },
        addConsentAnswer: (state, action: PayloadAction<IConsentAnswer>) => {
            return { ...state, consentAnswers: { ...state.consentAnswers, [action.payload.consentId]: action.payload } };
        },
        setAnonymize: (state, action) => {
            return {
                ...state,
                anonymize: action.payload
            };
        }
    }
});

const fillFormReducer = persistReducer(
    {
        key: 'rtk:fillForm',
        storage
    },
    slice.reducer
);

export const { setAnonymize, resetFillForm, addConsentAnswer } = slice.actions;

const reducerObj = { reducerPath: slice.name, reducer: fillFormReducer };

export const selectAnonymize = (state: RootState) => state.fillForm.anonymize;

export default reducerObj;
