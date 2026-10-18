import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';

import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { IThemeState, useFormState } from '@app/store/jotai/form';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { getRespondentPlaceholder } from '@app/utils/form-utils';
import { useEffect, useState } from 'react';
import styled from 'styled-components';
import { useDebounceValue } from 'usehooks-ts';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
import { useQuestionLabel } from './question-label-context';
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
        // The style's pinned radius (Classic 6px, Sheet and Leaflet 4px, Studio square).
        borderRadius: styleTokens($formTheme?.style).inputRadius,
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

/** The text area, named by the question it sits in (QuestionWrapper's label context). */
function LabelledTextArea(props: React.ComponentProps<typeof StyledAutoSizeTextArea>) {
    const { control } = useQuestionLabel();
    return <StyledAutoSizeTextArea {...props} {...control} />;
}

export default function TextAreaField({ field }: { field: StandardFormFieldDto }) {
    const { formResponse, addFieldTextAnswer, addFieldEmailAnswer, addFieldNumberAnswer, addFieldURLAnswer, removeAnswer } = useFormResponse();
    const [inputVal, setInputVal] = useState((formResponse.answers && formResponse.answers[field.id]?.text) || '');

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
            {/* No form of its own (Enter in a text area starts a new line, so
                one never submitted anyway). */}
            <LabelledTextArea
                $formTheme={theme}
                rows={1}
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                // leaving the field (e.g. to click Submit) must not wait for the debounce
                onBlur={() => commit(inputVal)}
                className="border px-4 py-3 text-base leading-normal outline-hidden transition-shadow lg:text-lg lg:leading-7"
                style={{
                    resize: 'none'
                }}
                id={`input-field-${field.id}`}
                placeholder={field?.properties?.placeholder || getRespondentPlaceholder(field.type, t)}
            />
        </QuestionWrapper>
    );
}
