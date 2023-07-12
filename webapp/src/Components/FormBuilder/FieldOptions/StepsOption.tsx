import React, { ChangeEvent, useState } from 'react';

import { MenuItem } from '@mui/material';
import { useDispatch } from 'react-redux';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addField } from '@app/store/form-builder/slice';
import { FormFieldState } from '@app/store/form-builder/types';

export default function StepsOption({ field }: { field: FormFieldState }) {
    const dispatch = useDispatch();
    const onStepsChange = (event: ChangeEvent<HTMLInputElement>) => {
        if (parseInt(event.target.value) > 25) return;
        dispatch(addField({ ...field, properties: { ...field.properties, steps: event.target.value } }));
    };

    const onBlur = (event: ChangeEvent<HTMLInputElement>) => {
        if (!event.target.value) dispatch(addField({ ...field, properties: { ...field.properties, steps: 5 } }));
    };

    return (
        <>
            {field.tag === FormBuilderTagNames.INPUT_RATING && (
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px' }} className="flex items-center justify-between body4 !text-black-700 !bg-white hover:bg-white">
                    <div>
                        Steps <span className="text-gray-600 text-xs">(Max: 25)</span>
                    </div>
                    <input
                        type="number"
                        max={25}
                        onBlur={onBlur}
                        aria-errormessage={'Max allowed is 25'}
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
