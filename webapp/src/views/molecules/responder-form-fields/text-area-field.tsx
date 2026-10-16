import { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';

import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { getRespondentPlaceholder } from '@app/utils/form-utils';
import { scrollToDivById } from '@app/utils/scroll-utils';
import { useEffect, useState } from 'react';
import styled from 'styled-components';
import { useDebounceValue } from 'usehooks-ts';
import QuestionWrapper from './question-wrapper';

const StyledAutoSizeTextArea = styled(AutosizeTextarea)<{
    $slide?: StandardFormFieldDto;
    $formTheme?: IThemeState;
}>(({ $formTheme }) => {
    // Theme is passed as a prop; calling the useFormState() hook inside a
    // styled-components interpolation produces an inconsistent hook count under
    // React 19 ("Rendered fewer hooks than expected").
    const themeColor = $formTheme?.tertiary;
    const secondaryColor = $formTheme?.secondary;
    return {
        // Same bordered treatment as every other input (see shadcn/ui/input.tsx):
        // white field, ink answer text, legible placeholder, visible focus ring.
        // Short/long text previously opted back into an underline-only look,
        // which fragmented the input language and had no focus indicator.
        background: '#ffffff',
        // Rest on the theme's border colour (3:1 on its ground); hover steps to
        // ink; focus commits to the action colour (matches shadcn/ui/input.tsx).
        borderColor: themeColor || '#818CA0',
        color: $formTheme?.primary,
        '&::placeholder': {
            color: '#667085 !important'
        },
        '&:hover:not(:focus)': {
            borderColor: $formTheme?.primary || '#101828'
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
    const { t } = useRespondentLanguage();
    const { theme } = useFormState();

    const [debouncedInputValue] = useDebounceValue(inputVal, 300);

    const commit = (value: string) => {
        if (!value) {
            removeAnswer(field.id);
            return;
        }
        addFieldTextAnswer(field.id, value);
    };

    useEffect(() => {
        commit(debouncedInputValue);
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
                    $formTheme={theme}
                    rows={1}
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    // leaving the field (e.g. to click Submit) must not wait for the debounce
                    onBlur={() => commit(inputVal)}
                    className="rounded-md border px-4 py-3 text-base leading-normal outline-hidden transition-shadow lg:text-lg lg:leading-7"
                    style={{
                        resize: 'none'
                    }}
                    id={`input-field-${field.id}`}
                    placeholder={field?.properties?.placeholder || getRespondentPlaceholder(field.type, t)}
                />
            </form>
        </QuestionWrapper>
    );
}
