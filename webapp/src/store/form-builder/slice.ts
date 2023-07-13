import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { PayloadAction, createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import ansiRegex from 'ansi-regex';
import ObjectID from 'bson-objectid';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import { QUESTION_TYPE } from '@app/components/form/renderer/form-renderer';
import { StandardFormQuestionDto } from '@app/models/dtos/form';
import { FormBuilderTagNames, getFormBuilderTagNameFromString } from '@app/models/enums/formBuilder';
import { IBuilderState, IFormFieldState } from '@app/store/form-builder/types';
import { getInitialPropertiesForFieldType } from '@app/store/form-builder/utils';
import { RootState } from '@app/store/store';

const initialState: IBuilderState = {
    id: '',
    title: '',
    description: '',
    fields: {},
    isFormDirty: false,
    activeFieldIndex: -1
};

export const setIsFormDirtyAsync = createAsyncThunk('form/setIsFormDirtyAsync', async (isDirty, { getState }) => {
    // Perform async logic here, e.g., making an API call or any other asynchronous operation
    // You can access the current state using `getState()`

    // Simulating an asynchronous operation with a delay
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Return the new value for isFormDirty
    return isDirty;
});

export const slice = createSlice({
    name: 'createForm',
    initialState,
    extraReducers: (builder) => {
        // Handling the async thunk action
        builder.addCase(setIsFormDirtyAsync.fulfilled, (state, action) => {
            // @ts-ignore
            state.isFormDirty = action.payload;
        });
    },
    reducers: {
        setIsFormDirty: (state, action) => {
            return { ...state, isFormDirty: action.payload };
        },
        setEditForm: (state, action) => {
            const fields: any = {};
            for (const field of action.payload.fields) {
                const choices: any = {};
                for (const choice of field?.properties?.choices || []) {
                    choices[choice.id] = choice;
                }
                fields[field.id] = { ...field, properties: { ...field.properties, choices: choices } };
            }
            return {
                ...state,
                formId: action.payload.formId,
                title: action.payload.title,
                description: action.payload.description,
                fields: fields
            };
        },
        setActiveFieldIndex: (state, action) => {
            return {
                ...state,
                activeFieldIndex: action.payload
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
        setBlockFocus: (state, action: PayloadAction<{ fieldId: string; isFocused: boolean }>) => {
            const { fieldId, isFocused } = action.payload;
            state.fields[fieldId].isFocused = isFocused;
        },
        updateField: (state, action) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.id]: action.payload
                }
            };
        },
        addFieldNewImplementation: (state, action) => {
            const { type, position, id } = action.payload;
            let newType = type;
            const fieldsToAdd: any = [];
            if (type.includes('question')) {
                newType = type.replace('question_', 'input_');
                fieldsToAdd.push({
                    id: uuidv4(),
                    type: FormBuilderTagNames.LAYOUT_HEADER3
                });
            }
            const newField: any = {
                id: uuidv4(),
                type: newType
            };
            newField.properties = getInitialPropertiesForFieldType(newType);
            fieldsToAdd.push(newField);
            const fieldsArray = Object.values(state.fields);
            fieldsArray.splice(position, !!id ? 0 : 1, fieldsToAdd);
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: any, index: number) => {
                newFieldsMap[field.id] = { ...field, index };
            });
            return {
                ...state,
                fields: newFieldsMap
            };
        },
        addQuestionAndAnswerField: (state, action) => {
            let { position, type, id } = action.payload;
            const newTag = type.replace('question_', 'input_');
            type = getFormBuilderTagNameFromString(newTag);
            const fields = { ...state.fields };
            fields[id] = {
                id: id,
                type: type
            };
            if (type === FormBuilderTagNames.INPUT_RATING) {
                fields[id]['properties'] = {
                    steps: 5
                };
            }
            if (
                type === FormBuilderTagNames.INPUT_MULTIPLE_CHOICE ||
                type === FormBuilderTagNames.INPUT_CHECKBOXES ||
                type === FormBuilderTagNames.INPUT_RANKING ||
                type === FormBuilderTagNames.INPUT_DROPDOWN ||
                type === FormBuilderTagNames.INPUT_MULTISELECT
            ) {
                const choiceId = uuidv4();
                fields[id]['properties'] = {};
                // @ts-ignore
                fields[id]['properties']['choices'] = {
                    [choiceId]: {
                        id: choiceId,
                        value: ''
                    }
                };
                if (type === FormBuilderTagNames.INPUT_CHECKBOXES || type === FormBuilderTagNames.INPUT_MULTISELECT) {
                    fields[id]['properties'] = {
                        ...(fields[id]['properties'] || {}),
                        allowMultipleSelection: true
                    };
                }
            }
            const fieldsArray = Object.values(fields);
            fieldsArray.splice(position, 0, {
                id: uuidv4(),
                type: FormBuilderTagNames.LAYOUT_HEADER3
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

export const selectIsFormDirty = (state: RootState) => state.createForm.isFormDirty;

export const selectFormBuilderFields = (state: RootState) => state.createForm.fields;
export const selectFormField = (id: string) => (state: RootState) => state.createForm.fields[id];

export const {
    setActiveFieldIndex,
    setIsFormDirty,
    addQuestionAndAnswerField,
    setFields,
    setEditForm,
    resetForm,
    deleteField,
    setFieldDescription,
    setFieldRequired,
    setFieldTitle,
    setFormDescription,
    setFieldType,
    updateField,
    setFormTitle,
    setBlockFocus
} = slice.actions;

export default reducerObj;
