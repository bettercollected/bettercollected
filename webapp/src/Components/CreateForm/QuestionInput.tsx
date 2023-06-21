import { useState } from 'react';

import { useDispatch } from 'react-redux';

import BetterInput from '@app/components/Common/input';
import { setFieldTitle } from '@app/store/create-form/slice';
import { FormFieldState } from '@app/store/create-form/types';

interface IQuestionInputProps {
    field: FormFieldState;
}

export default function QuestionInput({ field }: IQuestionInputProps) {
    const dispatch = useDispatch();
    const [value, setValue] = useState(field.title || '');
    return (
        <>
            <BetterInput
                value={value}
                className="bg-black-50"
                placeholder="Question Title"
                onChange={(event) => {
                    setValue(event.target.value);
                }}
                onBlur={() => {
                    dispatch(setFieldTitle({ fieldId: field.id, title: value }));
                }}
            />
        </>
    );
}
