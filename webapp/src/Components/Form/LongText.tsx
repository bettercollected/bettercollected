import React, { ChangeEvent } from 'react';

import { FieldRequired } from '@Components/UI/FieldRequired';
import { useDispatch } from 'react-redux';

import { FormInputField } from '@app/components/Common/input';
import { AnswerDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { addAnswer, deleteAnswer } from '@app/store/fill-form/slice';

interface ILongTextProps {
    field: StandardFormFieldDto;
    ans?: any;
    enabled?: boolean;
}

LongText.defaultProps = {
    enabled: false
};

export default function LongText({ ans, enabled, field }: ILongTextProps) {
    const dispatch = useDispatch();
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        const answer = {} as AnswerDto;
        answer.field = { id: field.id };
        answer.text = event.target.value;

        if (answer.text !== '') {
            dispatch(addAnswer(answer));
        } else {
            dispatch(deleteAnswer(answer));
        }
    };

    return (
        <div className="relative w-full h-full">
            {field?.validations?.required && <FieldRequired className="top-0.5 right-1" />}
            <FormInputField
                placeholder={field?.properties?.placeholder}
                multiline
                InputProps={{
                    style: {
                        padding: '12px 16px'
                    }
                }}
                inputProps={{
                    style: {
                        fontSize: 14
                    }
                }}
                sx={{
                    '& .MuiInputBase-input.Mui-disabled': {
                        WebkitTextFillColor: '#1D1D1D'
                    }
                }}
                minRows={3}
                maxRows={10}
                value={ans?.text || ans?.email || ans?.number || ans?.boolean || ans?.url || ans?.file_url || ans?.payment?.name}
                disabled={!enabled}
                fullWidth
                onChange={onChange}
                className="!mb-0"
            />
        </div>
    );
}
