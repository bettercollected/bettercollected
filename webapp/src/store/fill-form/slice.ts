import { createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { AnswerDto } from '@app/models/dtos/form';
import { FormValidationError } from '@app/store/fill-form/type';
import { RootState } from '@app/store/store';

interface FillIBuilderState {
    id: string;
    answers: {
        [fieldId: string]: AnswerDto;
    };
    invalidFields: Record<string, Array<FormValidationError>>;
}

const initialState: FillIBuilderState = {
    id: '',
    answers: {},
    invalidFields: {}
};

const slice = createSlice({
    name: 'fillForm',
    initialState: initialState,
    reducers: {
        resetFillForm: () => {
            return initialState;
        },
        addAnswer: (state, action) => {
            return {
                ...state,
                answers: {
                    ...state.answers,
                    [action.payload.field.id]: action.payload
                }
            };
        },
        deleteAnswer: (state, action) => {
            delete state.answers[action.payload.field.id];
        },
        setInvalidFields: (state, action) => {
            return {
                ...state,
                invalidFields: action.payload
            };
        }
    }
});

const fillFormReducer = persistReducer(
    {
        key: 'rtk:fillForm',
        storage,
        whitelist: ['value']
    },
    slice.reducer
);

export const { resetFillForm, setInvalidFields, deleteAnswer, addAnswer } = slice.actions;

const reducerObj = { reducerPath: slice.name, reducer: fillFormReducer };

export const selectAnswers = (state: RootState) => state.fillForm.answers;

export const selectAnswer = (fieldId: string) => (state: RootState) => state.fillForm.answers[fieldId];

export const selectInvalidFields = (state: RootState) => state.fillForm.invalidFields;

export default reducerObj;
