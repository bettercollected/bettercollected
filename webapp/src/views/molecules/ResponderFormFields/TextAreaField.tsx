import { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { getPlaceholderValueForField } from '@app/utils/formUtils';
import { scrollToDivById } from '@app/utils/scrollUtils';
import { useEffect, useState } from 'react';
import styled from 'styled-components';
import { useDebounceValue } from 'usehooks-ts';
import QuestionWrapper from './QuestionQwrapper';

const StyledAutoSizeTextArea = styled(AutosizeTextarea)<{
    $slide?: StandardFormFieldDto;
    $formTheme?: IThemeState;
}>(({}) => {
    const { theme } = useFormState();
    const themeColor = theme?.tertiary;
    const secondaryColor = theme?.secondary;
    return {
        background: 'inherit',
        borderColor: themeColor,
        color: secondaryColor,
        '&::placeholder': {
            color: `${themeColor} !important`
        },
        '&:focus': {
            borderColor: secondaryColor
        }
    };
});

export default function TextAreaField({ field }: { field: StandardFormFieldDto }) {
    const { formResponse, addFieldTextAnswer, addFieldEmailAnswer, addFieldNumberAnswer, addFieldURLAnswer, removeAnswer } = useFormResponse();
    const [inputVal, setInputVal] = useState((formResponse.answers && formResponse.answers[field.id]?.text) || '');

    const form: StandardFormDto = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const [debouncedInputValue] = useDebounceValue(inputVal, 300);

    useEffect(() => {
        if (!debouncedInputValue) {
            removeAnswer(field.id);
            return;
        }
        addFieldTextAnswer(field.id, debouncedInputValue);
    }, [debouncedInputValue]);

    return (
        <QuestionWrapper field={field}>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) scrollToDivById(form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
                }}
            >
                <StyledAutoSizeTextArea
                    rows={1}
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    className="rounded-none border-0 border-b-[1px] px-0 py-2 text-[28px] leading-tight lg:text-[32px]"
                    style={{
                        resize: 'none'
                    }}
                    id={`input-field-${field.id}`}
                    placeholder={field?.properties?.placeholder || getPlaceholderValueForField(field.type)}
                />
            </form>
        </QuestionWrapper>
    );
}
