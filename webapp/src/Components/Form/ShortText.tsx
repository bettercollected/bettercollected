import React, { ChangeEvent } from 'react';

import { useDispatch } from 'react-redux';

import BetterInput from '@app/components/Common/input';
import { AnswerDto, StandardFormQuestionDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addAnswer, deleteAnswer } from '@app/store/fill-form/slice';

interface IShortTextProps {
    field: StandardFormQuestionDto;
    ans?: any;
    enabled?: boolean;
}

ShortText.defaultProps = {
    enabled: false
};

export default function ShortText({ ans, enabled, field }: IShortTextProps) {
    const dispatch = useDispatch();
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        const answer = {} as AnswerDto;
        answer.field = { id: field.id };
        switch (field?.type) {
            case FormBuilderTagNames.INPUT_EMAIL:
                answer.email = event.target.value;
                break;
            case FormBuilderTagNames.INPUT_NUMBER:
                answer.number = parseInt(event.target.value);
                break;
            case FormBuilderTagNames.INPUT_LINK:
                answer.url = event.target.value;
                break;
            case FormBuilderTagNames.INPUT_DATE:
                answer.date = event.target.value;
                break;
            case FormBuilderTagNames.INPUT_PHONE_NUMBER:
                answer.phone_number = event.target.value;
                break;
            default:
                answer.text = event.target.value;
        }
        if (event.target.value !== '') {
            dispatch(addAnswer(answer));
        } else {
            dispatch(deleteAnswer(answer));
        }
    };

    return (
        // <StyledTextField>
        <BetterInput
            type={field?.type === 'email' ? 'email' : 'text'}
            value={ans?.text || ans?.email || ans?.number || ans?.boolean || ans?.url || ans?.file_url || ans?.payment?.name || ans?.date || ans?.phone_number}
            placeholder={field?.properties?.placeholder}
            disabled={!enabled}
            inputProps={{
                style: {
                    padding: 16,
                    fontSize: 14,
                    fontWeight: 400,
                    color: 'black',
                    content: 'none',
                    outline: 'gray'
                }
            }}
            className={`!mb-7 `}
            fullWidth
            onChange={onChange}
        />
        // </StyledTextField>
    );
}
