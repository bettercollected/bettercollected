import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import MuiSwitch from '@Components/Common/Input/Switch';
import Validation from '@Components/FormBuilder/FieldOptions/Validation';
import {ValidationType} from '@Components/FormBuilder/FieldOptions/types';
import {FormControlLabel, MenuItem} from '@mui/material';
import {useDispatch} from 'react-redux';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import {FormBuilderTagNames, NonInputFormBuilderTagNames} from '@app/models/enums/formBuilder';
import {setUpdateField} from '@app/store/form-builder/actions';
import {IFormFieldState} from '@app/store/form-builder/types';

interface IIndividualFieldOptionsProps {
    field: IFormFieldState;
}

export default function FormValidations({field}: IIndividualFieldOptionsProps) {
    const dispatch = useDispatch();
    const {t} = useBuilderTranslation();

    const handleFieldRequiredChange = (event: React.SyntheticEvent<Element, Event>, checked: boolean) => {
        event.preventDefault();
        event.stopPropagation();

        const fieldValidations = {...field.validations};
        fieldValidations.required = checked;
        dispatch(setUpdateField({...field, validations: fieldValidations}));
    };
    return (
        <>
            {!NonInputFormBuilderTagNames.includes(field?.type || FormBuilderTagNames.LAYOUT_SHORT_TEXT) && (
                <>
                    <Divider className="my-2"/>

                    <div className="flex flex-col gap-2 py-3">
                        <p className="px-5 text-xs font-semibold tracking-widest leading-none uppercase text-black-700">{t('COMPONENTS.VALIDATIONS.DEFAULT')}</p>
                    </div>
                    <MenuItem sx={{paddingX: '20px', paddingY: '10px'}}
                              className="flex items-center body4 !text-black-900">
                        <FormControlLabel
                            slotProps={{
                                typography: {
                                    fontSize: 14
                                }
                            }}
                            label={t('COMPONENTS.VALIDATIONS.REQUIRED')}
                            labelPlacement="start"
                            className="m-0 text-xs flex items-center justify-between w-full"
                            control={<MuiSwitch sx={{m: 1}} className="text-black-900 m-0" size="small"
                                                onChange={handleFieldRequiredChange}
                                                checked={!!field.validations?.required}/>}
                        />
                    </MenuItem>
                </>
            )}
            {(field?.type === FormBuilderTagNames.INPUT_SHORT_TEXT || field?.type === FormBuilderTagNames.INPUT_LONG_TEXT) && (
                <>
                    <Validation field={field} type={ValidationType.MAX_LENGTH}/>
                    <Validation field={field} type={ValidationType.MIN_LENGTH}/>
                    <Validation field={field} type={ValidationType.REGEX}/>
                </>
            )}
            {field?.type === FormBuilderTagNames.INPUT_NUMBER && (
                <>
                    <Validation field={field} type={ValidationType.MIN_VALUE}/>
                    <Validation field={field} type={ValidationType.MAX_VALUE}/>
                </>
            )}
            {field?.type === FormBuilderTagNames.INPUT_MULTISELECT ||
                field?.type === FormBuilderTagNames.INPUT_DROPDOWN ||
                (field?.type === FormBuilderTagNames.INPUT_CHECKBOXES && (
                    <>
                        <Validation field={field} type={ValidationType.MAX_CHOICES}/>
                        <Validation field={field} type={ValidationType.MIN_CHOICES}/>
                    </>
                ))}
        </>
    );
}
