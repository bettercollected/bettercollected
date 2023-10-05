import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import MuiSwitch from '@Components/Common/Input/Switch';
import StepsOption from '@Components/FormBuilder/FieldOptions/StepsOption';
import Validation from '@Components/FormBuilder/FieldOptions/Validation';
import { ValidationType } from '@Components/FormBuilder/FieldOptions/types';
import { useDispatch } from 'react-redux';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setUpdateField } from '@app/store/form-builder/actions';
import { IFormFieldState } from '@app/store/form-builder/types';

interface IIndividualFieldOptionsProps {
    field: IFormFieldState;
}

export default function FormValidations({ field }: IIndividualFieldOptionsProps) {
    const dispatch = useDispatch();
    const { t } = useBuilderTranslation();

    const handleFieldRequiredChange = (event: React.SyntheticEvent<Element, Event>, checked: boolean) => {
        event.preventDefault();
        event.stopPropagation();

        const fieldValidations = { ...field.validations };
        fieldValidations.required = checked;
        dispatch(setUpdateField({ ...field, validations: fieldValidations }));
    };
    return (
        <>
            {!NonInputFormBuilderTagNames.includes(field?.type || FormBuilderTagNames.LAYOUT_SHORT_TEXT) && (
                <>
                    <div className="my-4">
                        <Divider />
                    </div>
                    <div className="flex flex-col gap-2 py-3">
                        <p className="px-5 text-xs font-semibold tracking-widest leading-none text-black-700">Option</p>
                    </div>
                    <StepsOption field={field} />
                    <div className="px-4 flex w-full justify-between items-center py-2">
                        <span className="text-black-700">{t('COMPONENTS.VALIDATIONS.REQUIRED')}</span>
                        <MuiSwitch sx={{ m: 1 }} className="text-black-900 m-0" size="small" onChange={handleFieldRequiredChange} checked={!!field.validations?.required} />
                    </div>
                </>
            )}
            {(field?.type === FormBuilderTagNames.INPUT_SHORT_TEXT || field?.type === FormBuilderTagNames.INPUT_LONG_TEXT) && (
                <>
                    <Validation field={field} type={ValidationType.MAX_LENGTH} />
                    <Validation field={field} type={ValidationType.MIN_LENGTH} />
                    <Validation field={field} type={ValidationType.REGEX} />
                </>
            )}
            {field?.type === FormBuilderTagNames.INPUT_NUMBER && (
                <>
                    <Validation field={field} type={ValidationType.MIN_VALUE} />
                    <Validation field={field} type={ValidationType.MAX_VALUE} />
                </>
            )}
            {field?.type === FormBuilderTagNames.INPUT_MULTISELECT ||
                field?.type === FormBuilderTagNames.INPUT_DROPDOWN ||
                (field?.type === FormBuilderTagNames.INPUT_CHECKBOXES && (
                    <>
                        <Validation field={field} type={ValidationType.MAX_CHOICES} />
                        <Validation field={field} type={ValidationType.MIN_CHOICES} />
                    </>
                ))}
        </>
    );
}
