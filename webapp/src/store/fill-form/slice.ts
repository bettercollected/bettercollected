import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { RootState } from '@app/store/store';

interface FillFormState {
    anonymize?: boolean;
}

const initialState: FillFormState = {
    anonymize: false
};

const slice = createSlice({
    name: 'fillForm',
    initialState: initialState,
    reducers: {
        resetFillForm: () => {
            return initialState;
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

export const { setAnonymize, resetFillForm } = slice.actions;

const reducerObj = { reducerPath: slice.name, reducer: fillFormReducer };

export const selectAnonymize = (state: RootState) => state.fillForm.anonymize;

export default reducerObj;
