import { PayloadAction, createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import { v4 } from 'uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { IBuilderMenuState, IBuilderState, IFormFieldState } from '@app/store/form-builder/types';

import { getInitialPropertiesForFieldType } from './utils';

const firstFieldId = v4();

const initialState: IBuilderState = {
    id: '',
    title: '',
    description: '',
    menus: {
        spotlightField: { isOpen: false, afterFieldUuid: '' },
        commands: { isOpen: false, atFieldUuid: '' },
        fieldSettings: { isOpen: false, atFieldUuid: '' },
        pipingFields: { isOpen: false, atFieldUuid: '' },
        pipingFieldSettings: { isOpen: false, uuid: '' }
    },
    fields: {
        [firstFieldId]: {
            id: firstFieldId,
            type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
            isCommandMenuOpen: false,
            position: 0
        }
    },
    versions: [],
    currentVersionIndex: 0,
    isFormDirty: false,
    activeFieldIndex: -2,
    activeFieldId: ''
};

export const setIsFormDirtyAsync = createAsyncThunk('form/setIsFormDirtyAsync', async (isDirty, { getState }) => {
    // Perform async logic here, e.g., making an API call or any other asynchronous operation
    // You can access the current state using `getState()`

    // Simulating an asynchronous operation with a delay
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Return the new value for isFormDirty
    return isDirty;
});

export const builder = createSlice({
    name: 'builder',
    initialState,
    extraReducers: (builder) => {
        // Handling the async thunk action
        builder.addCase(setIsFormDirtyAsync.fulfilled, (state, action) => {
            // @ts-ignore
            state.isFormDirty = action.payload;
        });
    },
    reducers: {
        // Use this action to modify the values for:
        // id, title, description, versions, currentVersionIndex, isFormDirty, activeFieldIndex
        setBuilderState: (state: IBuilderState, action: { payload: Partial<IBuilderState>; type: string }) => {
            return {
                ...state,
                ...action.payload
            };
        },
        // current active/focused field
        setActiveField: (state, action: PayloadAction<{ id: string; position: number }>) => {
            return {
                ...state,
                activeFieldIndex: action.payload.position,
                activeFieldId: action.payload.id
            };
        },
        setBuilderMenuState: (state: IBuilderState, action: { payload: Partial<IBuilderMenuState>; type: string }) => {
            const menus = { ...state.menus, ...action.payload };
            return { ...state, menus };
        },
        resetBuilderMenuState: (state: IBuilderState) => {
            const menus = { ...state.menus, ...initialState.menus };
            return { ...state, menus };
        },
        setAddNewField: (state: IBuilderState, action: { payload: IFormFieldState; type: string }) => {
            const fieldsToAdd: Array<IFormFieldState> = [];
            const type = action.payload?.type;
            let newType = type;
            if (type.includes('question')) {
                // @ts-ignore
                newType = type.replace('question_', 'input_');
                fieldsToAdd.push({
                    id: v4(),
                    type: FormBuilderTagNames.LAYOUT_LABEL,
                    position: action.payload.position
                });
            }
            const newField: IFormFieldState = {
                ...action.payload,
                type: newType,
                position: action.payload.position
            };
            newField.properties = getInitialPropertiesForFieldType(newType);
            fieldsToAdd.push(newField);
            const fieldsArray = [...Object.values(state.fields)];

            fieldsArray.splice(action?.payload?.position + (action?.payload?.replace ? 0 : 1), action?.payload?.replace ? 1 : 0, ...fieldsToAdd);
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: IFormFieldState, index: number) => {
                newFieldsMap[field.id] = { ...field, position: index };
            });

            return { ...state, fields: newFieldsMap };
        },
        addDuplicateField: (state: IBuilderState, action: { payload: IFormFieldState; type: string }) => {
            // TODO: fix duplicate for shortcut keys
            const fieldsArray = [...Object.values(state.fields)];
            fieldsArray.splice(action?.payload?.position, 0, { ...action.payload });
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: IFormFieldState, index: number) => {
                newFieldsMap[field.id] = field;
                newFieldsMap[field.id].position = index;
            });
            state.fields = newFieldsMap;
            state.activeFieldIndex = action?.payload?.position;
        },
        setUpdateField: (state: IBuilderState, action: { payload: IFormFieldState; type: string }) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.id]: action.payload
                }
            };
        },
        setFields: (state: IBuilderState, action: { payload: Array<IFormFieldState>; type: string }) => {
            const fields: Record<string, IFormFieldState> = {};
            action.payload.forEach((field: IFormFieldState, position: number) => {
                fields[field.id] = { ...field, position };
            });
            return {
                ...state,
                fields: fields
            };
        },
        setDeleteField: (state: IBuilderState, action: { payload: string; type: string }) => {
            const fields = { ...state.fields };
            delete fields[action.payload];
            const fieldsArray = [...Object.values(fields)];
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: IFormFieldState, index: number) => {
                newFieldsMap[field.id] = field;
                newFieldsMap[field.id].position = index;
            });

            state.fields = newFieldsMap;
            state.isFormDirty = true;
        },
        setEditForm: (state, action) => {
            const fields: any = {};
            action.payload.fields.forEach((field: any, index: number) => {
                const choices: any = {};
                for (const choice of field?.properties?.choices || []) {
                    choices[choice.id] = choice;
                }
                fields[field.id] = { ...field, position: index, properties: { ...field.properties, choices: choices } };
            });
            return {
                ...state,
                id: action.payload.formId,
                title: action.payload.title,
                description: action.payload.description,
                activeFieldIndex: -2,
                activeFieldId: 'field-title',
                fields: fields
            };
        },
        setMoveField: (state: IBuilderState, action: PayloadAction<{ oldIndex: number; newIndex: number }>) => {
            const { oldIndex, newIndex } = action.payload;
            const fields = { ...state.fields };
            const fieldsArray = [...Object.values(fields)];
            const movedField = fieldsArray.splice(oldIndex, 1)[0];
            fieldsArray.splice(newIndex, 0, movedField);
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: IFormFieldState, index: number) => {
                newFieldsMap[field.id] = field;
                newFieldsMap[field.id].position = index;
            });

            state.fields = newFieldsMap;
            state.isFormDirty = true;
            state.activeFieldIndex = newIndex;

            state.activeFieldId = Object.keys(fieldsArray).at(newIndex) ?? '';
        },

        resetForm: (state) => {
            return initialState;
        }
    }
});

const builderPersistReducer = persistReducer(
    {
        key: 'rtk:builder',
        storage,
        whitelist: ['value']
    },
    builder.reducer
);

const reducerObj = { reducerPath: builder.name, reducer: builderPersistReducer };
export default reducerObj;
