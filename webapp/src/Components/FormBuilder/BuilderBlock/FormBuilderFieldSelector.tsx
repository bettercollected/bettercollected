import React from 'react';

import { batch } from 'react-redux';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetBuilderMenuState, setUpdateField } from '@app/store/form-builder/actions';
import { selectActiveFieldIndex, selectFields, selectMenuState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { convertPlaceholderToDisplayValue, getPreviousField } from '@app/utils/formBuilderBlockUtils';

export default function FormBuilderFieldSelector({ field }: { field: IFormFieldState }) {
    const pipingFieldMenuState: any = useAppSelector(selectMenuState('pipingFields'));

    const formFields = useAppSelector(selectFields);

    const dispatch = useAppDispatch();
    const fields = Object.values(formFields);
    const activeFieldPosition = useAppSelector(selectActiveFieldIndex);
    const getFilteredInputFields = () => {
        const filteredFields: Array<any> = [];
        fields.forEach((field) => {
            if (field.type.includes('input_') && ![FormBuilderTagNames.INPUT_FILE_UPLOAD, FormBuilderTagNames.INPUT_RANKING].includes(field?.type) && field?.position < activeFieldPosition) {
                const x: any = {
                    fieldId: field.id
                };
                const previousField = getPreviousField(fields, field);
                let text = field?.properties?.placeholder;
                if (LabelFormBuilderTagNames.includes(previousField?.type)) {
                    text = previousField?.value;
                }
                x.value = convertPlaceholderToDisplayValue(fields, text);
                x.type = field.type;
                filteredFields.push(x);
            }
        });
        return filteredFields;
    };

    const replaceLastAt = (inputString: string, replacement: string) => {
        const lastAtIndex = inputString.lastIndexOf('@');

        if (lastAtIndex !== -1) {
            return inputString.substring(0, lastAtIndex) + replacement + inputString.substring(lastAtIndex + 1);
        }
        return inputString;
    };
    const onClickField = (inputField: any) => {
        batch(() => {
            dispatch(
                setUpdateField({
                    ...field,
                    value: replaceLastAt(field.value || '', `{{ ${inputField.fieldId} }}`)
                })
            );
            dispatch(resetBuilderMenuState());
        });
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
                <div className="text-gray-600 font-bold px-4 py-2 ">Mention a field</div>
                <div className="flex flex-col">
                    {getFilteredInputFields().map((inputField: any) => (
                        <div
                            className={`px-4 py-2 cursor-pointer truncate hover:bg-black-100 text-base font-normal bg-white text-black-800`}
                            key={inputField.fieldId}
                            onClick={() => {
                                onClickField(inputField);
                            }}
                        >
                            {inputField?.value}
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
}
