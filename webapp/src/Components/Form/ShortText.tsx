import React, { ChangeEvent, useEffect } from 'react';

import { FieldRequired } from '@Components/UI/FieldRequired';
import { useDispatch } from 'react-redux';

import BetterInput from '@app/components/Common/input';
import { AnswerDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { selectAuth } from '@app/store/auth/slice';
import { addAnswer, deleteAnswer, selectFormResponderOwnerField } from '@app/store/fill-form/slice';
import { useAppSelector } from '@app/store/hooks';

interface IShortTextProps {
    field: StandardFormFieldDto;
    ans?: any;
    enabled?: boolean;
}

ShortText.defaultProps = {
    enabled: false
};

export default function ShortText({ ans, enabled, field }: IShortTextProps) {
    const dispatch = useDispatch();

    const responseDataOwnerField = useAppSelector(selectFormResponderOwnerField);

    const auth = useAppSelector(selectAuth);
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

    useEffect(() => {
        if (responseDataOwnerField === field?.id && auth) {
            console.log(auth, responseDataOwnerField, field.id);
            const answer = {} as AnswerDto;
            answer.field = { id: field.id };
            answer.email = auth.email;
            dispatch(addAnswer(answer));
        }
    }, [responseDataOwnerField, auth]);

    const getInputType = () => {
        switch (field?.type) {
            case FormBuilderTagNames.INPUT_EMAIL:
                return 'email';
            case FormBuilderTagNames.INPUT_NUMBER:
                return 'number';
            case FormBuilderTagNames.INPUT_DATE:
                return 'date';
            default:
                return 'text';
        }
    };

    return (
        <div className="relative">
            <BetterInput
                type={getInputType()}
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
            {field?.validations?.required && <FieldRequired className="top-0.5 right-1" />}
        </div>
    );
}
