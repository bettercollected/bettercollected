import { Fragment } from 'react';

import { RadioGroup } from '@headlessui/react';
import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { Check } from '@app/views/atoms/Icons/Check';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { scrollToDivById } from '@app/utils/scrollUtils';
import QuestionWrapper from './QuestionQwrapper';

const StyledDiv = styled.div<{ $theme: any }>(({ $theme }) => {
    const secondaryColor = $theme?.secondary;
    return {
        '&:hover': {
            borderColor: secondaryColor + '!important'
        }
    };
});

const YesNoField = ({ field }: { field: StandardFormFieldDto }) => {
    const { addFieldBooleanAnswer, formResponse } = useFormResponse();
    const { theme } = useFormState();

    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const getValue = () => {
        if (formResponse?.answers?.[field.id]?.boolean !== null || formResponse?.answers?.[field.id]?.boolean !== undefined) return formResponse?.answers?.[field.id]?.boolean;
        else return null;
    };

    return (
        <QuestionWrapper field={field}>
            <RadioGroup
                value={getValue()}
                className={'flex w-min flex-col gap-2'}
                onChange={(value) => {
                    addFieldBooleanAnswer(field.id, !!value);
                    setTimeout(() => {
                        if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) scrollToDivById(form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
                    }, 200);
                }}
            >
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        return (
                            <RadioGroup.Option value={choice.value === 'Yes'} key={index} as={Fragment}>
                                {({ active, checked }) => {
                                    return (
                                        <StyledDiv
                                            $theme={theme}
                                            style={{
                                                borderColor: theme?.tertiary,
                                                background: active || checked ? theme?.tertiary : '',
                                                color: theme?.secondary
                                            }}
                                            className={`flex w-[100px] cursor-pointer justify-between rounded-xl border p-2 px-4`}
                                        >
                                            {choice.value}
                                            {checked && <Check />}
                                        </StyledDiv>
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
