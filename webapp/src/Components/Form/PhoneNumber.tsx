import { useState } from 'react';

import { E164Number } from 'libphonenumber-js';
import PhoneInput from 'react-phone-input-2';
import { useDispatch } from 'react-redux';

import { AnswerDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { addAnswer, deleteAnswer } from '@app/store/fill-form/slice';

interface IPhoneNumberProps {
    field: StandardFormFieldDto;
    ans?: any;
    enabled?: boolean;
}

export default function PhoneNumber({ ans, enabled, field }: IPhoneNumberProps) {
    const dispatch = useDispatch();
    const [isTyping, setIsTyping] = useState(false);

    const onChange = (value?: E164Number) => {
        const answer = {} as AnswerDto;
        answer.field = { id: field.id };
        answer.phone_number = value;
        if (value && value !== '') {
            setIsTyping(true);
            dispatch(addAnswer(answer));
        } else {
            setIsTyping(false);
            dispatch(deleteAnswer(answer));
        }
    };

    return (
        <PhoneInput
            inputClass={'focus:shadow-input focus:!border-2 focus:!border-brand-200'}
            inputProps={{ id: `input-${field.id}` }}
            inputStyle={{ WebkitTextFillColor: isTyping ? '' : '#AAAAAA' }}
            disabled={!enabled}
            placeholder={field?.properties?.placeholder}
            value={ans?.phone_number}
            onChange={onChange}
        />
    );
}
