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

    const onChange = (value?: E164Number) => {
        const answer = {} as AnswerDto;
        answer.field = { id: field.id };
        answer.phone_number = value;
        if (value && value !== '') {
            dispatch(addAnswer(answer));
        } else {
            dispatch(deleteAnswer(answer));
        }
    };

    return <PhoneInput disabled={!enabled} placeholder={field?.properties?.placeholder} value={ans?.phone_number} onChange={onChange} />;
}