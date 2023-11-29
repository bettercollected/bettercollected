import React, { useEffect, useState } from 'react';

import ConditionalListDropDown from '@Components/FormBuilder/Conditionals/ConditionalListDropDown';
import ConditionalOptionsDropdown from '@Components/FormBuilder/Conditionals/ConditionalOptionsDropdown';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addAction, deleteAction, updateAction } from '@app/store/form-builder/actions';
import { selectFields } from '@app/store/form-builder/selectors';
import { ActionType, ConditionalActions, IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { checkShowAllFields, convertFieldForConditionalDropDownState } from '@app/utils/conditionalUtils';
import { getNextField, getPreviousField } from '@app/utils/formBuilderBlockUtils';

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

    const fields = Object.values(formFields);

    const shouldDisplayAllFields = checkShowAllFields(action?.type || ActionType.SHOW_FIELDS);

    const getFilteredFields = () => {
        const filteredFields: Array<any> = [];
        fields.forEach((field: IFormFieldState) => {
            let convertedField = {};
            if (shouldDisplayAllFields) {
                convertedField = convertFieldForConditionalDropDownState(field);
            } else {
                if (field?.type.startsWith('input_')) {
                    const previousField = getPreviousField(fields, field);
                    convertedField = convertFieldForConditionalDropDownState(previousField, field.id);
                } else {
                    return;
                }
            }
            if (field?.type !== FormBuilderTagNames.CONDITIONAL) {
                filteredFields.push(convertedField);
            }
        });
        return filteredFields;
    };

    const [inputFields, setInputFields] = useState<any>(getFilteredFields());
    const dispatch = useAppDispatch();

    useEffect(() => {
        const filteredFields = getFilteredFields();
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
                } else if (!previousSelectedFields?.includes(nextField?.id) && !currentSelectedFields.includes(nextField?.id) && currentSelectedFields.includes(selectedField?.id) && previousSelectedFields?.includes(selectedField?.id)) {
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
        dispatch(
            updateAction({
                fieldId: field.id,
                actionId: action.id,
                data: {
                    ...action,
                    payload: shouldDisplayAllFields ? handleFieldSelection(payload).map((field: any) => field.fieldId) : payload.map((field: any) => field.fieldId)
                }
            })
        );
    };

    const onActionTypeChange = (changedActionType: any) => {
        dispatch(
            updateAction({
                fieldId: field.id,
                actionId: action.id,
                data: {
                    ...action,
                    type: changedActionType.type,
                    payload: []
                }
            })
        );
    };

    const selectedConditionalFields = inputFields.filter((item: any) => field?.properties?.actions && field?.properties?.actions[action.id]?.payload?.includes(item?.fieldId));

    const handleAddAction = () => {
        dispatch(addAction(field.id));
    };
    const handleRemoveAction = (action: any) => {
        dispatch(deleteAction({ fieldId: field.id, actionId: action.id }));
    };

    return (
        <div className={'flex flex-col gap-1 md:gap-2  rounded-lg'}>
            <h1 className={'text-pink-500 text-sm'}>{action?.position == 0 ? 'THEN' : 'AND'}</h1>
            <div className={'flex justify-between items-center'}>
                <div className={'flex flex-col lg:flex-row gap-2 w-[calc(100%-3rem)]'}>
                    <ConditionalListDropDown size={'small'} value={actions.find((state) => state.type == action.type) || null} onChange={onActionTypeChange} items={actions} />
                    <ConditionalListDropDown showIcons={true} value={selectedConditionalFields} onChange={onPayloadChange} items={inputFields} multiple />
                </div>
                <ConditionalOptionsDropdown showRemoveOption={Object.keys(field.properties?.actions || {}).length > 1} addOption={handleAddAction} removeOption={() => handleRemoveAction(action)} text={'action'} />
            </div>
        </div>
    );
};
export default React.memo(ThenBlock);
