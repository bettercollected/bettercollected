import React, { useEffect, useState } from 'react';

import ConditionalListDropDown from '@Components/FormBuilder/Conditionals/ConditionalListDropDown';
import ConditionalListMultipleSelectDropDown from '@Components/FormBuilder/Conditionals/ConditionalListMultipleSelectDropDown';

import { LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { updateAction } from '@app/store/form-builder/actions';
import { selectBuilderState, selectFields } from '@app/store/form-builder/selectors';
import { ActionType, ConditionalActions, IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { getPreviousField } from '@app/utils/formBuilderBlockUtils';

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
    const [actionType, setActionType] = useState({ type: '', value: 'State' });
    const [selectedFields, setSelectedFields] = useState<any>([]);
    const dispatch = useAppDispatch();

    const getCurrentField = () => {
        return fields.find((field: IFormFieldState) => field.id === state.activeFieldId);
    };

    useEffect(() => {
        const filteredFields: Array<any> = [];
        fields.forEach((field) => {
            if (field.type.includes('input_')) {
                const x: any = {
                    fieldId: field.id
                };
                const previousField = getPreviousField(fields, field);
                let text = field?.properties?.placeholder;
                if (LabelFormBuilderTagNames.includes(previousField?.type)) {
                    text = previousField?.value;
                }
                x.value = text;
                filteredFields.push(x);
            }
        });
        setInputFields(filteredFields);
    }, [fields.length]);

    useEffect(() => {
        if (actionType.type) {
            const currentField = getCurrentField();
            const actionId = currentField?.properties?.actions && Object.keys(currentField.properties.actions)[0];
            dispatch(
                updateAction({
                    fieldId: currentField?.id,
                    actionId: actionId,
                    data: { payload: selectedFields.map((field: any) => field.fieldId), type: actionType.type }
                })
            );
        }
    }, [selectedFields]);

    return (
        <div className={'flex flex-col gap-2 p-4 bg-new-white-200 rounded-lg'}>
            <h1 className={'text-pink-500 text-sm'}>THEN</h1>
            <div className={'flex flex-row gap-2 '}>
                {/*<ConditionalListDropDown size={'small'} selectedState={actionType} setSelectedState={setActionType} items={actions} />*/}
                <ConditionalListMultipleSelectDropDown selectedState={selectedFields} setSelectedState={setSelectedFields} items={inputFields} multiple />
            </div>
        </div>
    );
};

export default ThenBlock;
