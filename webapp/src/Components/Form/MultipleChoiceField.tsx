import React from 'react';

import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
import { FieldRequired } from '@Components/UI/FieldRequired';
import Radio from '@mui/material/Radio';
import { enableES5 } from 'immer';
import { useDispatch } from 'react-redux';

import { addAnswer, selectAnswer } from '@app/store/fill-form/slice';
import { useAppSelector } from '@app/store/hooks';


export default function MultipleChoiceField({ field, ans, enabled }: FormFieldProps) {
    const dispatch = useDispatch();
    const answer = useAppSelector(selectAnswer(field.id));
    const handleSelectChoice = (choice: any) => {
        if (enabled) {
            const answer: any = {};
            answer.field = { id: field.id };
            answer.choice = { value: choice.id };
            dispatch(addAnswer(answer));
        }
    };

    const checkValue = !(ans?.choice.value || '').match('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$');

    return (
        <div className="!mb-0 flex flex-col gap-3">
            {(field?.properties?.choices || []).map((choice: any, index: number) => (
                <div key={choice?.id} className={`flex relative w-fit items-center ${enabled ? 'cursor-pointer' : ''} ${!enableES5}`} onClick={() => handleSelectChoice(choice)}>
                    {index === 0 && field?.validations?.required && <FieldRequired className="-right-5" />}
                    <Radio
                        sx={{
                            '&, &.Mui-checked.Mui-disabled': {
                                color: '#4D4D4D'
                            }
                        }}
                        id={choice?.value}
                        className="!p-0 !rounded-full"
                        size="medium"
                        disabled={!enabled}
                        checked={!checkValue ? ans?.choice?.value === choice?.id || answer?.choice?.value === choice?.id : ans?.choice?.value === choice?.value || answer?.choice?.value === choice?.id}
                    />
                    <label htmlFor={choice?.value} className="!ml-2 body4">
                        {choice?.value}
                    </label>
                </div>
            ))}
        </div>
    );
}