import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { StandardFormDto } from '@app/models/dtos/form';

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
    questions: [],
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

export const { setForm, setFormSettings } = slice.actions;

export default reducerObj;
