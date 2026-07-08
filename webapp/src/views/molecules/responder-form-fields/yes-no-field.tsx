import { Fragment } from 'react';

import { RadioGroup } from '@headlessui/react';
import styled from 'styled-components';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { scrollToDivById } from '@app/utils/scroll-utils';
import { Check } from 'lucide-react';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import QuestionWrapper from './question-wrapper';

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
    const tokens = styleTokens(theme?.style);
    const { currentSlide } = useResponderState();

    // null (not undefined) when unanswered, so the RadioGroup stays controlled.
    const getValue = () => formResponse?.answers?.[field.id]?.boolean ?? null;

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
                                                // Selection = action-colour tint + border (solid fill with
                                                // white text in the studio style). Focus borders only —
                                                // painting the fill on `active` made keyboard focus look
                                                // like selection.
                                                borderColor: active || checked ? theme?.secondary : theme?.tertiary,
                                                background: tokens.solidSelection && checked ? theme?.secondary : checked ? theme?.secondary + '1A' : '',
                                                color: tokens.solidSelection && checked ? '#ffffff' : theme?.primary,
                                                borderRadius: tokens.inputRadius
                                            }}
                                            className={`flex min-w-[100px] max-w-full cursor-pointer items-center justify-between gap-2 border p-2 px-4 transition duration-150`}
                                        >
                                            {choice.value}
                                            {checked && <Check className="h-5 w-5 shrink-0" style={{ color: tokens.solidSelection ? '#ffffff' : theme?.secondary }} />}
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
