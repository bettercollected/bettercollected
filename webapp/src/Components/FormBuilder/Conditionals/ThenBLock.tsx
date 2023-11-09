import React, { useEffect, useState } from 'react';

import ConditionalListDropDown from '@Components/FormBuilder/Conditionals/ConditionalListDropDown';

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
    const dispatch = useAppDispatch();

    useEffect(() => {
        const filteredFields: Array<any> = [];
        fields.forEach((field: IFormFieldState) => {
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
    }, [formFields]);

    const onPayloadChange = (payload: any) => {
        dispatch(
            updateAction({
                fieldId: field.id,
                actionId: action.id,
                data: { ...action, payload: payload.map((field: any) => field.fieldId) }
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

    const selectedFields = inputFields.filter((item: any) => field?.properties?.actions && field?.properties?.actions[action.id]?.payload?.includes(item.fieldId));

    return (
        <div className={'flex flex-col gap-2 p-4 bg-new-white-200 rounded-lg'}>
            <h1 className={'text-pink-500 text-sm'}>THEN</h1>
            <div className={'flex flex-row gap-2 '}>
                <ConditionalListDropDown size={'small'} value={actions.find((state) => state.type == action.type)} onChange={onActionTypeChange} items={actions} />
                <ConditionalListDropDown value={selectedFields} onChange={onPayloadChange} items={inputFields} multiple />
            </div>
        </div>
    );
};

export default ThenBlock;
