import React from 'react';

import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
import { FieldRequired } from '@Components/UI/FieldRequired';
import Checkbox from '@mui/material/Checkbox';

import { addAnswer, deleteAnswer, selectAnswer } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

export default function CheckboxField({ field, ans, enabled }: FormFieldProps) {
    const dispatch = useAppDispatch();
    const answer = useAppSelector(selectAnswer(field.id));
    const answerChoices = answer?.choices?.values;

    const handleSelectChoice = (choice: any) => {
        const answer: any = {};
        answer.field = { id: field.id };
        if (answerChoices?.includes(choice?.id)) {
            const tempAnswers = [...answerChoices];
            tempAnswers.splice(answerChoices?.indexOf(choice?.id), 1);
            if (tempAnswers.length === 0) {
                dispatch(deleteAnswer(answer));
                return;
            }
            answer.choices = {
                values: [...tempAnswers]
            };
        } else {
            answer.choices = { values: [...(answerChoices || []), choice?.id] };
        }
        dispatch(addAnswer(answer));
    };

    return (
        <div className="!mb-0 flex flex-col gap-3">
            {(field?.properties?.choices || []).map((choice: any, index: number) => (
                <div key={choice?.id} className="flex w-fit  items-center relative">
                    {index === 0 && field?.validations?.required && <FieldRequired className="-right-5" />}
                    <Checkbox
                        sx={{
                            '&, &.Mui-checked.Mui-disabled': {
                                color: '#4D4D4D'
                            }
                        }}
                        id={choice?.id}
                        className="!p-0"
                        size="medium"
                        disabled={!enabled}
                        checked={!!ans?.choices?.values?.includes(choice?.id) || !!answerChoices?.includes(choice?.id) || !!ans?.choices?.values?.includes(choice?.value) || !!answerChoices?.includes(choice?.value)}
                        onClick={() => handleSelectChoice(choice)}
                    />
                    <label htmlFor={choice?.value} className="!ml-2 body4">
                        {choice?.value}
                    </label>
                </div>
            ))}
        </div>
    );
}
