import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { PayloadAction, createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import undoable from 'redux-undo';
import { v4 } from 'uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { Condition, ConditionalActions, IBuilderMenuState, IBuilderState, IChoiceFieldState, IFormFieldState } from '@app/store/form-builder/types';
import { convertProxyToObject } from '@app/utils/reduxUtils';

import { getInitialPropertiesForFieldType } from './utils';

const firstFieldId = v4();

export const initBuilderState: IBuilderState = {
    id: '',
    title: '',
    description: '',
    buttonText: 'Submit',
    menus: {
        spotlightField: { isOpen: false, afterFieldUuid: '' },
        commands: { isOpen: false, atFieldUuid: '', position: 'down' },
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
    activeFieldId: '',
    activeChoiceId: '',
    activeChoiceIndex: 0
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
    initialState: initBuilderState,
    extraReducers: (builder) => {
        // Handling the async thunk action
        builder.addCase(setIsFormDirtyAsync.fulfilled, (state, action) => {
            // @ts-ignore
            state.isFormDirty = action.payload;
        });
    },
    reducers: {
        // addDuplicateField
        addDuplicateField: (state: IBuilderState, action: { payload: IFormFieldState; type: string }) => {
            // TODO: fix duplicate for shortcut keys
            const fieldsArray = [...Object.values(state.fields)];
            fieldsArray.splice(action?.payload?.position, 0, { ...action.payload });
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: IFormFieldState, index: number) => {
                newFieldsMap[field.id] = field;
                newFieldsMap[field.id].position = index;
                ``;
            });
            state.fields = newFieldsMap;
            state.activeFieldIndex = action?.payload?.position;
        },
        // setActiveChoice
        setActiveChoice: (state, action: PayloadAction<{ id: string; position: number }>) => {
            const { id, position } = action.payload;
            state.activeChoiceId = id;
            state.activeChoiceIndex = position;
        },
        // setActiveField
        setActiveField: (state, action: PayloadAction<{ id: string; position: number }>) => {
            return {
                ...state,
                activeFieldIndex: action.payload.position,
                activeFieldId: action.payload.id
            };
        },
        // setAddNewChoice
        setAddNewChoice: (
            state: IBuilderState,
            action: {
                payload: { fieldId?: string; choice: IChoiceFieldState };
                type: string;
            }
        ) => {
            const activeField = state.fields[action.payload?.fieldId ? action.payload?.fieldId : state.activeFieldId];
            const newChoices = Object.values(convertProxyToObject(activeField.properties?.choices || {}));
            newChoices.splice(action.payload.choice.position, 0, { ...action.payload.choice });
            const choices: any = {};
            newChoices.forEach((choice: any, index: number) => {
                choices[choice.id] = { ...choice, position: index };
            });
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [activeField.id]: {
                        ...activeField,
                        properties: {
                            ...activeField.properties,
                            choices,
                            activeChoiceId: action.payload.choice.id,
                            activeChoiceIndex: action.payload.choice.position
                        }
                    }
                }
            };
        },
        // setAddNewField
        setAddNewField: (state: IBuilderState, action: { payload: IFormFieldState; type: string }) => {
            const fieldsToAdd: Array<IFormFieldState> = [];
            const type = action.payload?.type;
            let newType = type;
            let newFieldId = action.payload.id;
            if (type.includes('question')) {
                // @ts-ignore
                newType = type.replace('question_', 'input_');
                newFieldId = v4();
                fieldsToAdd.push({
                    id: action.payload.id,
                    type: FormBuilderTagNames.LAYOUT_LABEL,
                    position: action.payload.position
                });
            }
            const newField: IFormFieldState = {
                ...action.payload,
                id: newFieldId,
                type: newType,
                position: action.payload.position
            };
            newField.properties = action.payload.properties || getInitialPropertiesForFieldType(newType);
            fieldsToAdd.push(newField);
            const fieldsArray = [...Object.values(state.fields)];

            fieldsArray.splice(action?.payload?.position + (action?.payload?.replace ? 0 : 1), action?.payload?.replace ? 1 : 0, ...fieldsToAdd);
            const newFieldsMap: any = {};
            fieldsArray.forEach((field: IFormFieldState, index: number) => {
                newFieldsMap[field.id] = { ...field, position: index };
            });
            return {
                ...state,
                activeFieldId: newField.id,
                activeFieldIndex: action.payload.position,
                fields: newFieldsMap
            };
        },
        // setBuilderMenuState
        setBuilderMenuState: (state: IBuilderState, action: { payload: Partial<IBuilderMenuState>; type: string }) => {
            const menus = { ...state.menus, ...action.payload };
            return { ...state, menus };
        },
        // setCommandMenuPosition
        setCommandMenuPosition: (state, action: { payload: 'up' | 'down' }) => {
            if (state.menus?.commands)
                return {
                    ...state,
                    menus: { ...state.menus, commands: { ...state.menus?.commands, position: action.payload } }
                };
        },
        // setDeleteChoice
        setDeleteChoice: (state: IBuilderState, action: { payload: string; type: string }) => {
            const activeField = state.fields[state.activeFieldId];
            const proxyKeys = Object.getOwnPropertyNames(activeField.properties?.choices ?? {});
            //@ts-ignore
            const choicesEntries = proxyKeys.map((key) => [key, activeField.properties?.choices[key]]);
            const choices = Object.fromEntries(choicesEntries);
            if (action.payload) delete choices[action.payload];
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [activeField.id]: {
                        ...activeField,
                        properties: {
                            activeChoiceId: activeField.properties?.activeChoiceId,
                            activeChoiceIndex: (activeField.properties?.activeChoiceIndex ?? -1) - 1,
                            choices
                        }
                    }
                }
            };
        },
        // setDeleteField
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
        // setEditForm
        setEditForm: (state, action) => {
            const fields: any = {};
            action.payload.fields?.forEach((field: any, index: number) => {
                if (field?.type === FormBuilderTagNames.CONDITIONAL) {
                    const conditions: Record<string, Condition> = {};
                    const actions: Record<string, ConditionalActions> = {};
                    field?.properties?.conditions?.map((condition: Condition, position: number) => {
                        const id = uuidv4();
                        conditions[id] = { ...condition, id, position };
                    });
                    field?.properties?.actions?.map((action: ConditionalActions, position: number) => {
                        const id = uuidv4();
                        actions[id] = { ...action, id, position };
                    });
                    fields[field.id] = {
                        ...field,
                        position: index,
                        properties: { ...field.properties, conditions, actions }
                    };
                } else {
                    const choices: any = {};
                    field?.properties?.choices?.map((choice: IChoiceFieldState, index: number) => {
                        choices[choice.id] = { ...choice, position: index };
                    });
                    fields[field.id] = { ...field, position: index, properties: { ...field.properties, choices: choices } };
                }
            });
            return {
                ...state,
                id: action.payload.formId,
                title: action.payload.title,
                logo: action.payload.logo,
                coverImage: action.payload.coverImage,
                description: action.payload.description,
                buttonText: action.payload.buttonText || 'Submit',
                activeFieldIndex: -2,
                activeFieldId: 'field-title',
                settings: {
                    responseDataOwnerField: action.payload.settings?.responseDataOwnerField || ''
                },
                fields: fields
            };
        },
        // setFields
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
        // setIdentifierField
        setIdentifierField: (state, action) => {
            return {
                ...state,
                settings: {
                    responseDataOwnerField: action.payload
                }
            };
        },
        // setIsFormDirty
        setIsFormDirty: (state, action: PayloadAction<boolean>) => {
            state.isFormDirty = action.payload;
        },
        // setMoveField
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
        // setResetBuilderMenuState
        resetBuilderMenuState: (state: IBuilderState) => {
            const menus = { ...state.menus, ...initBuilderState.menus };
            return { ...state, menus };
        },
        // setResetForm
        resetForm: (state) => {
            return initBuilderState;
        },
        // setSetTyping
        setSetTyping: (state: IBuilderState, action: PayloadAction<boolean>) => {
            return {
                ...state,
                isTyping: action.payload
            };
        },
        // setUpdateCommandField
        setUpdateCommandField: (state: IBuilderState, action: { payload: IFormFieldState; type: string }) => {
            return {
                ...state,
                fields: {
                    ...state.fields,
                    [action.payload.id]: action.payload
                }
            };
        },
        // setUpdateField
        setUpdateField: (state: IBuilderState, action: { payload: IFormFieldState; type: string }) => {
            return {
                ...state,
                isTyping: true,
                fields: {
                    ...state.fields,
                    [action.payload.id]: action.payload
                }
            };
        },
        // setBuilderState
        setBuilderState: (state: IBuilderState, action: { payload: Partial<IBuilderState>; type: string }) => {
            return {
                ...state,
                ...action.payload
            };
        },
        // setTyping
        setTyping: (state: IBuilderState, action: PayloadAction<boolean>) => {
            return {
                ...state,
                isTyping: action.payload
            };
        },
        updateAction: (state: IBuilderState, action: PayloadAction<any>) => {
            const { fieldId, actionId, data } = action.payload;
            if (state.fields[fieldId].properties && state.fields[fieldId]?.properties?.actions) {
                // @ts-ignore
                state.fields[fieldId].properties.actions[actionId] = data;
            }
        },
        updateConditional: (
            state: IBuilderState,
            action: PayloadAction<{
                fieldId: string;
                conditionalId: string;
                data: Condition;
            }>
        ) => {
            const { fieldId, conditionalId, data } = action.payload;
            if (state.fields[fieldId]?.properties?.conditions) {
                state.fields[fieldId]!.properties!.conditions![conditionalId] = data;
            }
        },
        updateConditionalOperator: (state: IBuilderState, action: PayloadAction<any>) => {
            const { fieldId, operator } = action.payload;
            if (state.fields[fieldId]?.properties?.logicalOperator) {
                state.fields[fieldId].properties!.logicalOperator = operator;
            }
        },
        addCondition: (state: IBuilderState, action) => {
            const fieldId = action.payload;
            const conditionId = uuidv4();
            if (state.fields[fieldId]!.properties!.conditions)
                state.fields[fieldId]!.properties!.conditions![conditionId] = {
                    id: conditionId,
                    value: '',
                    position: Object.keys(state.fields[fieldId]?.properties?.conditions || {}).length
                };
        },
        deleteCondition: (state, action) => {
            const { fieldId, conditionId } = action.payload;
            if (Object.keys(state.fields[fieldId]?.properties?.conditions || {}).length > 1) delete state.fields[fieldId]!.properties!.conditions![conditionId];
        },
        addAction: (state: IBuilderState, action) => {
            const fieldId = action.payload;
            const actionId = uuidv4();
            if (state.fields[fieldId]!.properties!.actions)
                state.fields[fieldId]!.properties!.actions![actionId] = {
                    id: actionId,
                    payload: [],
                    position: Object.keys(state.fields[fieldId]?.properties?.actions || {}).length
                };
        },
        deleteAction: (state, action) => {
            const { fieldId, actionId } = action.payload;
            if (Object.keys(state.fields[fieldId]?.properties?.actions || {}).length > 1) delete state.fields[fieldId]!.properties!.actions![actionId];
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

const undoableReducer = undoable(builderPersistReducer, {
    neverSkipReducer: true,
    ignoreInitialState: true,
    filter: function filterActions(action, currentState, previousHistory) {
        if (currentState.isTyping) return false;
        return [builder.actions.setAddNewField.type, builder.actions.setAddNewChoice.type, builder.actions.setTyping.type].includes(action.type);
    }
});

const reducerObj = { reducerPath: builder.name, reducer: undoableReducer };
export default reducerObj;
