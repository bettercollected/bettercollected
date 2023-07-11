import { useState } from 'react';

import { Select, SelectChangeEvent } from '@mui/material';
import MenuItem from '@mui/material/MenuItem';

import { StandardFormQuestionDto } from '@app/models/dtos/form';
import { addAnswer, selectAnswer, selectAnswers } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

export default function DropdownField({ field }: { field: StandardFormQuestionDto }) {
    const dispatch = useAppDispatch();
    const answer = useAppSelector(selectAnswer(field.id));
    const onChange = (event: SelectChangeEvent<any>) => {
        const answer: any = {};
        answer.field = { id: field.id };
        answer.choice = { value: event?.target?.value };
        dispatch(addAnswer(answer));
    };

    return (
        <Select
            MenuProps={{
                style: { zIndex: 35001 }
            }}
            value={answer?.choice?.value || ''}
            onChange={onChange}
            className="w-fit mt-3 min-w-[200px] mb-3 text-black-900 !bg-white"
        >
            {field?.properties?.choices?.map((choice: any) => (
                <MenuItem key={choice.id} value={choice?.value}>
                    {choice.value}
                </MenuItem>
            ))}
        </Select>
    );
}
