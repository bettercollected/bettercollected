import React, { ChangeEvent } from 'react';

import { MenuItem } from '@mui/material';
import { useDispatch } from 'react-redux';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setUpdateField } from '@app/store/form-builder/actions';
import { IFormFieldState } from '@app/store/form-builder/types';

export default function StepsOption({ field }: { field: IFormFieldState }) {
    const dispatch = useDispatch();
    const { t } = useBuilderTranslation();
    const onStepsChange = (event: ChangeEvent<HTMLInputElement>) => {
        if (parseInt(event.target.value) > 25) return;
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, steps: parseInt(event.target.value) } }));
    };

    const onBlur = (event: ChangeEvent<HTMLInputElement>) => {
        if (!event.target.value) dispatch(setUpdateField({ ...field, properties: { ...field.properties, steps: 5 } }));
    };

    return (
        <>
            {field?.type === FormBuilderTagNames.INPUT_RATING && (
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px' }} className="flex items-center justify-between body4 !text-black-700 !bg-white hover:bg-white">
                    <div>
                        {t('COMPONENTS.OPTIONS.STEPS')} <span className="text-gray-600 text-xs">({t('COMPONENTS.OPTIONS.MAX')}: 25)</span>
                    </div>
                    <input
                        type="number"
                        max={25}
                        onBlur={onBlur}
                        onChange={onStepsChange}
                        value={field.properties?.steps}
                        className=" max-w-[50px] border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-min p-2.5 "
                        placeholder=""
                    />
                </MenuItem>
            )}
        </>
    );
}
