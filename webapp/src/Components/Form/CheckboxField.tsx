import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
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
        <>
            {(field?.properties?.choices || []).map((choice: any) => (
                <div key={choice?.id} className="flex items-center ">
                    <Checkbox disabled={!enabled} checked={!!ans?.choices?.values?.includes(choice?.value) || !!answerChoices?.includes(choice?.value)} onClick={() => handleSelectChoice(choice)} />
                    <div>{choice?.value}</div>
                </div>
            ))}
        </>
    );
}
