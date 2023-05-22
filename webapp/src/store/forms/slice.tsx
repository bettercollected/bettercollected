import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { Plans } from '@app/models/dtos/UserDto';
import { StandardFormDto } from '@app/models/dtos/form';
import { RootState } from '@app/store/store';

export const initialFormState: StandardFormDto = {
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
        roles: []
    },
    importerDetails: {
        email: '',
        roles: [],
        plan: Plans.FREE
    },
    fields: [],
    modifiedTime: ''
};

export const slice = createSlice({
    name: 'form',
    initialState: initialFormState,
    reducers: {
        setForm: (state, action) => {
            return { ...action.payload };
        },
        setFormSettings: (state, action) => {
            return { ...state, settings: action.payload };
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
export const { setForm, setFormSettings } = slice.actions;

export default reducerObj;
