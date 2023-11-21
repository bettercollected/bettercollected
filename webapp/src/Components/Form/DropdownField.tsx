import React from 'react';

import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { Select, SelectChangeEvent } from '@mui/material';
import MenuItem from '@mui/material/MenuItem';

import { addAnswer, selectAnswer } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

export default function DropdownField({ field, ans, enabled }: FormFieldProps) {
    const dispatch = useAppDispatch();
    const answer = useAppSelector(selectAnswer(field.id));
    const onChange = (event: SelectChangeEvent<any>) => {
        const answer: any = {};
        answer.field = { id: field.id };
        answer.choice = { value: event?.target?.value };
        dispatch(addAnswer(answer));
    };

    const checkValue = !(ans?.choice.value || '').match('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$');

    return (
        <div className="relative w-fit">
            {field?.validations?.required && <FieldRequired className=" -right-5" />}
            <Select
                size="small"
                MenuProps={{
                    style: { zIndex: 35001 }
                }}
                sx={{
                    '.MuiSelect-select.Mui-disabled': {
                        WebkitTextFillColor: '#1D1D1D'
                    }
                }}
                style={{
                    paddingTop: '3.5px',
                    paddingBottom: '3.5px',
                    paddingLeft: '2px',
                    fontSize: '14px'
                }}
                defaultValue={ans?.choice.value}
                disabled={!enabled}
                value={ans?.choice.value || answer?.choice?.value || ''}
                onChange={onChange}
                className="w-fit min-w-[167px] !rounded-md !border-gray-600 !mb-0 text-black-900 !bg-white"
            >
                {field?.properties?.choices?.map((choice: any, index: number) => (
                    <MenuItem key={choice.id} value={checkValue ? choice?.value : choice?.id} className="relative">
                        {choice.value}
                    </MenuItem>
                ))}
            </Select>
        </div>
    );
}
