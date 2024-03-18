import { Fragment } from 'react';

import { get } from 'lodash';

import { RadioGroup } from '@headlessui/react';

import { FormField } from '@app/models/dtos/form';
import { useFormTheme } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { Check } from '@app/views/atoms/Icons/Check';

import QuestionWrapper from './QuestionQwrapper';

const YesNoField = ({ field }: { field: FormField }) => {
    const { addFieldBooleanAnswer, formResponse } = useFormResponse();
    const theme = useFormTheme();

    const getValue = () => {
        if (
            formResponse?.answers?.[field.id]?.boolean !== null ||
            formResponse?.answers?.[field.id]?.boolean !== undefined
        )
            return formResponse?.answers?.[field.id]?.boolean;
        else return null;
    };
    return (
        <QuestionWrapper field={field}>
            <RadioGroup
                value={getValue()}
                className={'flex w-full flex-col gap-2'}
                onChange={(value) => addFieldBooleanAnswer(field.id, !!value)}
            >
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        return (
                            <RadioGroup.Option
                                value={choice.value === 'Yes'}
                                key={index}
                                as={Fragment}
                            >
                                {({ active, checked }) => {
                                    return (
                                        <div
                                            style={{
                                                borderColor: theme?.tertiary,
                                                background:
                                                    active || checked
                                                        ? theme?.tertiary
                                                        : ''
                                            }}
                                            className={`flex cursor-pointer justify-between rounded-xl border p-2 px-4 hover:!border-black-900`}
                                        >
                                            {choice.value}
                                            {checked && <Check />}
                                        </div>
                                    );
                                }}
                            </RadioGroup.Option>
                        );
                    })}
            </RadioGroup>
        </QuestionWrapper>
    );
};

export default YesNoField;
