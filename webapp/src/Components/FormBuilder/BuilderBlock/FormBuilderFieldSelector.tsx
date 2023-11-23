import React from 'react';

import TickIcon from '@app/components/icons/tick-icon';
import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { selectFields, selectMenuState } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';
import { getPreviousField } from '@app/utils/formBuilderBlockUtils';

export default function FormBuilderFieldSelector() {
    const pipingFieldMenuState: any = useAppSelector(selectMenuState('pipingFields'));

    const formFields = useAppSelector(selectFields);

    const fields = Object.values(formFields);
    const getFilteredInputFields = () => {
        const filteredFields: Array<any> = [];
        fields.forEach((field) => {
            if (field.type.includes('input_') && ![FormBuilderTagNames.INPUT_FILE_UPLOAD, FormBuilderTagNames.INPUT_RANKING].includes(field?.type)) {
                const x: any = {
                    fieldId: field.id
                };
                const previousField = getPreviousField(fields, field);
                let text = field?.properties?.placeholder;
                if (LabelFormBuilderTagNames.includes(previousField?.type)) {
                    text = previousField?.value;
                }
                x.value = text;
                x.type = field.type;
                filteredFields.push(x);
            }
        });
        return filteredFields;
    };

    return (
        <>
            <div
                style={{
                    position: 'fixed',
                    left: pipingFieldMenuState?.pos?.left,
                    top: pipingFieldMenuState?.pos?.top + 24
                }}
                className={`max-h-48 p-2 rounded absolute w-[300px] bg-white drop-shadow-lg top-full z-[100]`}
            >
                <div className="text-gray-600 font-bold">Mention a field</div>
                <div className="flex flex-col">
                    {getFilteredInputFields().map((inputField: any) => (
                        <div className={`px-4 py-2 cursor-pointer truncate text-base font-normal bg-white text-black-800`} key={inputField.fieldId}>
                            {inputField?.value}
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
}
