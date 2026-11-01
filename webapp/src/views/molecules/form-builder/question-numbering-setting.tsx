'use client';

import { useTranslation } from 'react-i18next';
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
    const { t } = useTranslation('builder');
    const { formFields, setShowQuestionNumbersOnAllPages } = useFormFieldsAtom();
    const { theme } = useFormState();
    const state = formNumberingState(formFields);
    const leaflet = styleTokens(theme?.style).key === 'leaflet';

    const hint = leaflet
        ? t('NUMBERING.HINT_LEAFLET')
        : state === 'mixed'
          ? t('NUMBERING.HINT_MIXED')
          : t('NUMBERING.HINT');

    return (
        <InspectorSection title={t('NUMBERING.TITLE')}>
            <SettingSwitch label={t('NUMBERING.LABEL')} checked={state === 'on'} onCheckedChange={(checked) => setShowQuestionNumbersOnAllPages(checked)} hint={hint} />
        </InspectorSection>
    );
}
