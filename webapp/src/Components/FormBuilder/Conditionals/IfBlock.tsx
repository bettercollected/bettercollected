import React, { useEffect, useState } from 'react';

import ConditionalListDropDown from '@Components/FormBuilder/Conditionals/ConditionalListDropDown';

import { LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { selectFields } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';
import { getPreviousField } from '@app/utils/formBuilderBlockUtils';

const IfBlock = ({ field }: { field: IFormFieldState }) => {
    const formFields = useAppSelector(selectFields);

    const fields = Object.values(formFields);

    const [inputFields, setInputFields] = useState<any>([]);

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
    }, [fields]);

    return (
        <div className={'flex flex-col gap-2 p-4 rounded-lg bg-new-white-200'}>
            <h1 className={'text-pink-500 text-sm'}>IF</h1>
            <div className={'flex flex-row gap-2 '}>
                <ConditionalListDropDown
                    defaultValue={inputFields.length > 0 ? inputFields[0] : undefined}
                    items={inputFields}
                    labelPicker={(item: any) => {
                        return item?.value;
                    }}
                />
                {/*<ConditionalListDropDown size={'small'} defaultValue={Comparisons[0]} items={Comparisons} />*/}
                {/*<ConditionalListDropDown defaultValue={{ value: 'Value' }} items={People} />*/}
            </div>
        </div>
    );
};

export default IfBlock;
