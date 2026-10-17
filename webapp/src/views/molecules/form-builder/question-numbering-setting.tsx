'use client';

import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { formNumberingState } from '@app/utils/question-numbering';
import { InspectorSection, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

/**
 * "Number questions": numbers respondents see before each question, for
 * the whole form (stored on every question page, see
 * utils/question-numbering.ts). The Leaflet style always numbers.
 */
export default function QuestionNumberingSetting() {
    const { formFields, setShowQuestionNumbersOnAllPages } = useFormFieldsAtom();
    const { theme } = useFormState();
    const state = formNumberingState(formFields);
    const leaflet = styleTokens(theme?.style).key === 'leaflet';

    const hint = leaflet
        ? 'The Leaflet style always numbers questions by section (1.1, 1.2, …). This applies when you switch to another style.'
        : state === 'mixed'
          ? 'Some pages are numbered and others are not. Switch on to number every page.'
          : 'Respondents see 1., 2., … before each question; with several pages, 2.1, 2.2, … by page.';

    return (
        <InspectorSection title="Numbering">
            <SettingSwitch label="Number questions" checked={state === 'on'} onCheckedChange={(checked) => setShowQuestionNumbersOnAllPages(checked)} hint={hint} />
        </InspectorSection>
    );
}
