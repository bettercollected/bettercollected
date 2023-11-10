import React, { useEffect, useState } from 'react';

import _ from 'lodash';

import ConditionalListDropDown from '@Components/FormBuilder/Conditionals/ConditionalListDropDown';
import ConditionalOptionsDropdown from '@Components/FormBuilder/Conditionals/ConditionalOptionsDropdown';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setUpdateField, updateAction } from '@app/store/form-builder/actions';
import { selectBuilderState, selectFields } from '@app/store/form-builder/selectors';
import { ActionType, ConditionalActions, IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewAction, getNextField, getPreviousField } from '@app/utils/formBuilderBlockUtils';

const actions = [
    { type: ActionType.SHOW_FIELDS, value: 'Show Field' },
    {
        type: ActionType.HIDE_FIELDS,
        value: 'Hide Field'
    },
    { type: ActionType.REQUIRE_ANSWERS, value: 'Make Require' }
];

const ThenBlock = ({ field, action }: { field: IFormFieldState; action: ConditionalActions }) => {
    const formFields = useAppSelector(selectFields);
    const state = useAppSelector(selectBuilderState);

    const fields = Object.values(formFields);

    const [inputFields, setInputFields] = useState<any>([]);
    const dispatch = useAppDispatch();

    const convertFieldForConditionalDropDownState = (field: any) => {
        let text = '';
        const x: any = {
            fieldId: field.id
        };
        if (LabelFormBuilderTagNames.includes(field?.type) && field?.value) {
            text = field?.value;
        } else if (!LabelFormBuilderTagNames.includes(field?.type) && field?.properties?.placeholder) {
            text = field?.properties?.placeholder;
        } else {
            text = _.startCase(field?.type.split('_').join(' '));
        }
        x.value = text;
        return x;
    };

    useEffect(() => {
        const filteredFields: Array<any> = [];
        fields.forEach((field: IFormFieldState) => {
            const convertedField = convertFieldForConditionalDropDownState(field);
            if (field?.type !== FormBuilderTagNames.CONDITIONAL) {
                filteredFields.push(convertedField);
            }
        });
        setInputFields(filteredFields);
    }, [formFields]);

    function handleFieldSelection(payload: any) {
        const previousSelectedFields = field?.properties?.actions && field?.properties?.actions[action.id]?.payload;
        const currentSelectedFields = payload.map((item: any) => item.fieldId);
        let selectedFields: Array<any> = [];
        payload.forEach((state: any) => {
            const selectedField = fields.find((field) => field.id == state.fieldId);

            if (selectedField?.type !== FormBuilderTagNames.CONDITIONAL) {
                selectedFields.push(state);
            }
            if (selectedField?.type === FormBuilderTagNames.LAYOUT_LABEL) {
                // for selecting 2 fields at one selection
                const nextField = selectedField && getNextField(fields, selectedField);
                if (!nextField?.type.startsWith('input_')) {
                    return;
                }
                if (previousSelectedFields?.includes(nextField?.id) && !currentSelectedFields.includes(nextField?.id)) {
                    return;
                } else {
                    selectedFields.push(convertFieldForConditionalDropDownState(getNextField(fields, selectedField)));
                }
            } else {
                // for removing 2 fields at one deSelection
                const previousField = selectedField && getPreviousField(fields, selectedField);
                if (!selectedField?.type.startsWith('input_')) {
                    return;
                }
                if (previousField?.type === FormBuilderTagNames.LAYOUT_LABEL && previousSelectedFields?.includes(previousField?.id) && !currentSelectedFields.includes(previousField?.id)) {
                    selectedFields.splice(selectedFields.indexOf(selectedField), 1);
                }
            }
        });
        return selectedFields;
    }

    const onPayloadChange = (payload: any) => {
        const selectedFields = handleFieldSelection(payload);
        dispatch(
            updateAction({
                fieldId: field.id,
                actionId: action.id,
                data: { ...action, payload: selectedFields.map((field: any) => field.fieldId) }
            })
        );
    };

    const onActionTypeChange = (changedActionType: any) => {
        dispatch(
            updateAction({
                fieldId: field.id,
                actionId: action.id,
                data: { ...action, type: changedActionType.type }
            })
        );
    };

    const selectedFields = inputFields.filter((item: any) => field?.properties?.actions && field?.properties?.actions[action.id]?.payload?.includes(item?.fieldId));
    const addCondition = () => {
        if (field?.properties?.actions) {
            const id = uuidv4();
            const position = action.position + 1;
            let actionsArray = Object.values(field?.properties?.actions);
            const newAction = createNewAction(id, position);
            actionsArray.splice(position, 0, newAction, ...actionsArray.slice(position));
            let newActionMap: any = {};
            actionsArray.forEach((item: any, index: number) => {
                const action = { ...item };
                action.position = index;
                newActionMap[action.id] = item;
            });
            dispatch(
                setUpdateField({
                    ...field,
                    properties: { ...field.properties, actions: newActionMap }
                })
            );
        }
    };
    const removeCondition = (action: any) => {
        if (field?.properties?.actions) {
            const actions = { ...field?.properties?.actions };
            delete actions[action.id];
            let actionsArray = Object.values(actions);
            actionsArray.forEach((item: any, index: number) => {
                const action = { ...item };
                action.position = index;
                actions[action.id] = action;
            });
            dispatch(
                setUpdateField({
                    ...field,
                    properties: { ...field.properties, actions }
                })
            );
        }
    };

    return (
        <div className={'flex flex-col gap-2 p-4 bg-new-white-200 rounded-lg'}>
            <h1 className={'text-pink-500 text-sm'}>THEN</h1>
            <div className={'flex flex-row gap-2 '}>
                <ConditionalListDropDown size={'small'} value={actions.find((state) => state.type == action.type)} onChange={onActionTypeChange} items={actions} />
                <ConditionalListDropDown value={selectedFields} onChange={onPayloadChange} items={inputFields} multiple />
                <ConditionalOptionsDropdown addOption={addCondition} removeOption={() => removeCondition(action)} text={'action'} />
            </div>
        </div>
    );
};
export default ThenBlock;
