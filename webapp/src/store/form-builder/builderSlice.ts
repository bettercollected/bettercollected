import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
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
    activeFieldIndex: -2
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
            // const fields = Object.values(state.fields);
            // const isFieldPositionExist = fields.filter((field) => field.position === action.payload.position).length > 0;
            // if (isFieldPositionExist && fields.length == 0) return { ...state };
            const type = action.payload?.type;
            let newType = type;
            if (type.includes('question')) {
                // @ts-ignore
                newType = type.replace('question_', 'input_');
                fieldsToAdd.push({
                    id: v4(),
                    type: FormBuilderTagNames.LAYOUT_HEADER3,
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
            const fieldsArray = Object.values(state.fields);
            fieldsArray.splice((action.payload?.position ?? 0) + 1 || (state.activeFieldIndex || 0) + 1 || fieldsArray.length, 0, ...fieldsToAdd);
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: IFormFieldState, index: number) => {
                newFieldsMap[field.id] = { ...field, position: index };
            });

            return { ...state, fields: newFieldsMap };
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
            action.payload.forEach((field: IFormFieldState) => {
                fields[field.id] = { ...field };
            });
            return {
                ...state,
                fields: fields
            };
        },
        setDeleteField: (state, action) => {
            delete state.fields[action.payload];
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
