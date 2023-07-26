import React from 'react';

import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
import { FieldRequired } from '@Components/UI/FieldRequired';
import Checkbox from '@mui/material/Checkbox';

import { StandardFormQuestionDto } from '@app/models/dtos/form';
import { addAnswer, selectAnswer, selectAnswers } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

export default function CheckboxField({ field, ans, enabled }: FormFieldProps) {
    const dispatch = useAppDispatch();
    const answer = useAppSelector(selectAnswer(field.id));
    const answerChoices = answer?.choices?.values;

    const handleSelectChoice = (choice: any) => {
        const answer: any = {};
        answer.field = { id: field.id };
        if (answerChoices?.includes(choice?.value)) {
            const tempAnswers = [...answerChoices];
            tempAnswers.splice(answerChoices?.indexOf(choice?.value), 1);
            answer.choices = {
                values: [...tempAnswers]
            };
        } else {
            answer.choices = { values: [...(answerChoices || []), choice?.value] };
        }
        dispatch(addAnswer(answer));
    };

    return (
        <div className="!mb-7 flex flex-col gap-3">
            {(field?.properties?.choices || []).map((choice: any, index: number) => (
                <div key={choice?.id} className="flex w-fit  items-center relative">
                    {index === 0 && field?.validations?.required && <FieldRequired className="-right-5" />}
                    <Checkbox className="!p-0" size="medium" disabled={!enabled} checked={!!ans?.choices?.values?.includes(choice?.value) || !!answerChoices?.includes(choice?.value)} onClick={() => handleSelectChoice(choice)} />
                    <div className="!ml-2">{choice?.value}</div>
                </div>
            ))}
        </div>
    );
}
