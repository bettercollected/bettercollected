import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { Plan } from '@app/models/dtos/UserStatus';
import { StandardFormDto } from '@app/models/dtos/form';
import { RootState } from '@app/store/store';
import { FormSlideLayout } from '@app/models/enums/form';

export const initFormState: StandardFormDto = {
    formId: '',
    title: '',
    description: '',
    createdTime: '',
    settings: {
        pinned: false,
        embedUrl: '',
        customUrl: '',
        private: false,
        provider: '',
        roles: [],
        disableBranding: false,
        hidden: false
    },
    importerDetails: {
        id: '',
        email: '',
        roles: [],
        plan: Plan.FREE
    },
    consent: [],
    fields: [],
    modifiedTime: '',
    groups: [],
    coverImage: '',
    logo: '',
    welcomePage: {
        title: '',
        layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
    },
    thankyouPage: [
        {
            layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
        }
    ],
    theme: {
        title: '',
        primary: '',
        secondary: '',
        tertiary: '',
        accent: ''
    }
};

export const slice = createSlice({
    name: 'form',
    initialState: initFormState,
    reducers: {
        setForm: (state, action) => {
            return { ...action.payload };
        },
        setFormSettings: (state, action) => {
            return { ...state, settings: action.payload };
        },
        resetSingleForm: () => {
            return initFormState;
        }
    }
});

const formReducer = persistReducer(
    {
        key: 'rtk:form',
        storage,
        whitelist: ['value']
    },
    slice.reducer
);

const reducerObj = { reducerPath: slice.name, reducer: formReducer };

export const selectForm = (state: RootState) => state.form;
export const { setForm, setFormSettings, resetSingleForm } = slice.actions;

export default reducerObj;
