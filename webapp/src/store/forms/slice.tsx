import { createSelector, createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { StandardFormDto } from '@app/models/dtos/form';
import { Plan } from '@app/models/dtos/user-status';
import { FormSlideLayout } from '@app/models/enums/form';
import { RootState } from '@app/store/store';
import { stripInternalFields } from '@app/utils/internal-fields';

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
            // A settings change answers with the workspace's settings for the
            // form, which do not hold the form's own language: keep it.
            const settings = action.payload;
            const keepLanguage = settings && typeof settings === 'object' && !('language' in settings) && state.settings?.language != null;
            return { ...state, settings: keepLanguage ? { ...settings, language: state.settings?.language } : settings };
        },
        /** The form's own language as the builder's document has it (null: none). */
        setFormLanguage: (state, action: { payload: string | null | undefined }) => {
            const language = action.payload ?? null;
            if ((state.settings?.language ?? null) === language) return state;
            return { ...state, settings: { ...state.settings, language } as StandardFormDto['settings'] };
        },
        /** The draft's organisation logo URL after an upload or removal (null: none). */
        setFormLogo: (state, action: { payload: string | null | undefined }) => {
            return { ...state, logo: action.payload || undefined };
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
/**
 * The form as respondents see it — internal fields removed. Every responder
 * surface (public page, preview) reads this, so a workspace member opening
 * their own form never sees staff-only fields either.
 */
export const selectResponderForm = createSelector([selectForm], (form) => stripInternalFields(form));
export const { setForm, setFormSettings, setFormLanguage, setFormLogo, resetSingleForm } = slice.actions;

export default reducerObj;
