import React, { ChangeEvent, useState } from 'react';

import MuiSwitch from '@Components/Common/Input/Switch';
import { ValidationType } from '@Components/FormBuilder/FieldOptions/types';
import { useDispatch } from 'react-redux';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { setUpdateField } from '@app/store/form-builder/actions';
import { IFormFieldState } from '@app/store/form-builder/types';

interface IValidationProps {
    type: ValidationType;
    field: IFormFieldState;
}

const getValidationLabel = (type: ValidationType) => {
    switch (type) {
        case ValidationType.MIN_LENGTH:
            return 'MIN_LENGTH';
        case ValidationType.MAX_LENGTH:
            return 'MAX_LENGTH';
        case ValidationType.MAX_VALUE:
            return 'MAX_VALUE';
        case ValidationType.MIN_VALUE:
            return 'MIN_VALUE';
        case ValidationType.MAX_CHOICES:
            return 'MAX_CHOICES';
        case ValidationType.MIN_CHOICES:
            return 'MIN_CHOICES';
        case ValidationType.REGEX:
            return 'REGEX';
        default:
            return '';
    }
};

export default function Validation({ field, type }: IValidationProps) {
    const [checked, setChecked] = useState(!!field?.validations && !!field?.validations[type]);
    const dispatch = useDispatch();
    const { t } = useBuilderTranslation();
    const handleValidationValueChange = (event: ChangeEvent<HTMLInputElement>) => {
        const fieldValidations: any = { ...field.validations };
        let value;
        if (type === ValidationType.REGEX) {
            value = event.target.value;
        } else {
            value = parseInt(event.target.value);
        }
        fieldValidations[type.toString()] = value;
        dispatch(setUpdateField({ ...field, validations: fieldValidations }));
    };

    return (
        <div className="flex px-5 py-2  flex-col">
            <div className="flex body4 w-full justify-between">
                <span className="!text-gray">{t('COMPONENTS.VALIDATIONS.' + getValidationLabel(type))}</span>
                <MuiSwitch
                    checked={checked}
                    onChange={() => {
                        setChecked(!checked);
                    }}
                />
            </div>
            {checked && (
                <input
                    onChange={handleValidationValueChange}
                    value={!!field?.validations && !!field?.validations[type] ? field?.validations[type] : ''}
                    type={type === ValidationType.REGEX ? 'text' : 'number'}
                    placeholder={t('COMPONENTS.VALIDATIONS.' + (type === ValidationType.REGEX ? 'ENTER_REGEX' : 'ENTER_NUMBER'))}
                    className="rounded-md mt-2 py-2 px-4 outline:none border border-black-600 !text-black-900"
                />
            )}
        </div>
    );
}
