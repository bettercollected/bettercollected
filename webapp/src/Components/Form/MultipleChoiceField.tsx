import { FormFieldProps } from '@Components/Form/BetterCollectedForm';
import Radio from '@mui/material/Radio';
import { useDispatch } from 'react-redux';

import { addAnswer, selectAnswers } from '@app/store/fill-form/slice';
import { useAppSelector } from '@app/store/hooks';

export default function MultipleChoiceField({ field, ans }: FormFieldProps) {
    const dispatch = useDispatch();
    const answers = useAppSelector(selectAnswers);
    const handleSelectChoice = (choice: any) => {
        const answer: any = {};
        answer.field = { id: field.id };
        answer.choice = { value: choice.value };
        dispatch(addAnswer(answer));
    };
    return (
        <>
            {(field?.properties?.choices || []).map((choice: any) => (
                <div key={choice?.id} className="flex items-center cursor-pointer" onClick={() => handleSelectChoice(choice)}>
                    <Radio checked={answers[field.id]?.choice?.value === choice?.value} />
                    <div>{choice?.value}</div>
                </div>
            ))}
        </>
    );
}
