import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
import Radio from '@mui/material/Radio';
import { enableES5 } from 'immer';
import { useDispatch } from 'react-redux';

import { addAnswer, selectAnswer, selectAnswers } from '@app/store/fill-form/slice';
import { useAppSelector } from '@app/store/hooks';

export default function MultipleChoiceField({ field, ans, enabled }: FormFieldProps) {
    const dispatch = useDispatch();
    const answer = useAppSelector(selectAnswer(field.id));
    const handleSelectChoice = (choice: any) => {
        if (enabled) {
            const answer: any = {};
            answer.field = { id: field.id };
            answer.choice = { value: choice.value };
            dispatch(addAnswer(answer));
        }
    };
    return (
        <>
            {(field?.properties?.choices || []).map((choice: any) => (
                <div key={choice?.id} className={`flex items-center ${enabled ? 'cursor-pointer' : ''} ${!enableES5}`} onClick={() => handleSelectChoice(choice)}>
                    <Radio disabled={!enabled} checked={ans?.choice?.value === choice?.value || answer?.choice?.value === choice?.value} />
                    <div>{choice?.value}</div>
                </div>
            ))}
        </>
    );
}
