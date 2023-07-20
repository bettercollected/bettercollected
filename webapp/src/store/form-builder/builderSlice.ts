import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import { v4 } from 'uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { IBuilderMenuState, IBuilderState, IFormFieldState } from '@app/store/form-builder/types';

import { getInitialPropertiesForFieldType } from './utils';

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
    fields: {},
    versions: [],
    currentVersionIndex: 0,
    isFormDirty: false,
    activeFieldIndex: 0
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
                    type: FormBuilderTagNames.LAYOUT_HEADER3
                });
            }
            const newField: IFormFieldState = {
                ...action.payload,
                type: newType
            };
            newField.properties = getInitialPropertiesForFieldType(newType);
            fieldsToAdd.push(newField);
            const fieldsArray = Object.values(state.fields);
            fieldsArray.splice((action.payload?.position ?? 0) + 1 || (state.activeFieldIndex || 0) + 1 || fieldsArray.length, 0, ...fieldsToAdd);
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: any) => {
                newFieldsMap[field.id] = field;
            });

            return { ...state, fields: newFieldsMap };
        },
        setFields: (state: IBuilderState, action: { payload: Array<IFormFieldState>; type: string }) => {
            const fields: Record<string, IFormFieldState> = {};
            action.payload.forEach((field: IFormFieldState) => {
                fields[field.id] = { ...field };
            });
            return {
                ...state,
                fields: fields
            };
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
