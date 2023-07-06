import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { createSlice } from '@reduxjs/toolkit';
import ansiRegex from 'ansi-regex';
import ObjectID from 'bson-objectid';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { QUESTION_TYPE } from '@app/components/form/renderer/form-renderer';
import { StandardFormQuestionDto } from '@app/models/dtos/form';
import { FormBuilderTagNames, getFormBuilderTagNameFromString } from '@app/models/enums/formBuilder';
import { FormFieldState, FormState } from '@app/store/form-builder/types';
import { RootState } from '@app/store/store';

const initialState: FormState = {
    title: '',
    description: '',
    fields: {}
};
export const slice = createSlice({
    name: 'createForm',
    initialState,
    reducers: {
        setEditForm: (state, action) => {
            const fields: any = {};
            for (const field of action.payload.fields) {
                fields[field.id] = field;
            }
            return {
                title: action.payload.title,
                description: action.payload.description,
                fields: fields
            };
        },
        resetForm: (state) => {
            return initialState;
        },
        setFormTitle: (state, action) => {
            return {
                ...state,
                title: action.payload
            };
        },
        setFormDescription: (state, action) => {
            return {
                ...state,
                description: action.payload
            };
        },
        addField: (state, action) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.id]: action.payload
                }
            };
        },
        addQuestionAndAnswerField: (state, action) => {
            let { position, tag, id } = action.payload;
            const newTag = tag.replace('question_', 'input_');
            tag = getFormBuilderTagNameFromString(newTag);
            const fields = { ...state.fields };
            fields[id] = {
                id: id,
                tag: tag
            };
            if (tag === FormBuilderTagNames.INPUT_RATING) {
                fields[id]['properties'] = {
                    steps: 5
                };
            }
            if (tag === FormBuilderTagNames.INPUT_MULTIPLE_CHOICE || tag === FormBuilderTagNames.INPUT_CHECKBOXES || tag === FormBuilderTagNames.INPUT_RANKING || tag === FormBuilderTagNames.INPUT_DROPDOWN || tag === FormBuilderTagNames.INPUT_MULTISELECT) {
                const choiceId = uuidv4();
                fields[id]['choices'] = {
                    [choiceId]: {
                        id: choiceId,
                        value: ''
                    }
                };
                if (tag === FormBuilderTagNames.INPUT_CHECKBOXES || tag === FormBuilderTagNames.INPUT_MULTISELECT) {
                    fields[id]['properties'] = {
                        allowMultipleSelection: true
                    };
                }
            }
            const fieldsArray = Object.values(fields);
            fieldsArray.splice(position, 0, {
                id: uuidv4(),
                tag: FormBuilderTagNames.LAYOUT_HEADER3
            });
            const newFields: any = {};
            fieldsArray.forEach((field: any, index: number) => {
                newFields[field.id] = { ...field, index };
            });
            return {
                ...state,
                fields: newFields
            };
        },
        deleteField: (state, action) => {
            delete state.fields[action.payload];
        },
        setFieldRequired: (state, action) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.fieldId]: {
                        ...state.fields[action.payload.fieldId],
                        validations: {
                            required: action.payload.required
                        }
                    }
                }
            };
        },
        setFieldType: (state, action) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.fieldId]: {
                        ...state.fields[action.payload.fieldId],
                        type: action.payload.type
                    }
                }
            };
        },
        setFieldTitle: (state, action) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.fieldId]: {
                        ...state.fields[action.payload.fieldId],
                        title: action.payload.title
                    }
                }
            };
        },
        setFieldDescription: (state, action) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.fieldId]: {
                        ...state.fields[action.payload.fieldId],
                        description: action.payload.description
                    }
                }
            };
        },
        setFields: (state, action) => {
            const fields: any = {};
            action.payload.forEach((field: any, index: number) => {
                fields[field.id] = { ...field, index };
            });
            return {
                ...state,
                fields: fields
            };
        }
    }
});

const createFormReducer = persistReducer(
    {
        key: 'rtk:form',
        storage,
        whitelist: ['value']
    },
    slice.reducer
);

const reducerObj = { reducerPath: slice.name, reducer: createFormReducer };

export const selectCreateForm = (state: RootState) => state.createForm;

export const selectFormBuilderFields = (state: RootState) => state.createForm.fields;
export const selectFormField = (id: string) => (state: RootState) => state.createForm.fields[id];

export const { addQuestionAndAnswerField, setFields, setEditForm, resetForm, deleteField, setFieldDescription, setFieldRequired, setFieldTitle, setFormDescription, setFieldType, addField, setFormTitle } = slice.actions;

export default reducerObj;
