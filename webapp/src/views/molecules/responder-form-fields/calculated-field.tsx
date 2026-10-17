import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { calculatedAnswerValue, formatCalculatedValue } from '@app/utils/calculated-fields';

import QuestionWrapper from './question-wrapper';

/**
 * A calculated value as respondents see it: the field's label and the value
 * computed from their answers so far, read-only, formatted per the field's
 * format in the form's language. The value is a polite live region labelled
 * by the field's title, so a screen reader announces it when it changes.
 * Fields hidden from respondents never get here (form-slide.tsx).
 */
export default function CalculatedField({ field }: { field: StandardFormFieldDto }) {
    const { formResponse } = useFormResponse();
    const { theme } = useFormState();
    const { t, language } = useRespondentLanguage();
    const value = calculatedAnswerValue(formResponse.answers?.[field.id]);
    const text = typeof value === 'boolean' ? t(value ? 'FIELD.CALCULATED_TRUE' : 'FIELD.CALCULATED_FALSE') : formatCalculatedValue(value, field.properties?.format, language);

    return (
        <QuestionWrapper field={field}>
            <output
                id={`calculated-${field.id}`}
                aria-live="polite"
                aria-atomic="true"
                aria-labelledby={`q-title-${field.id} calculated-${field.id}`}
                data-testid="calculated-value"
                className="mt-2 block text-2xl font-semibold tabular-nums"
                style={{ color: theme?.primary }}
                lang={language}
            >
                {text ? text : <span className="text-base font-normal text-black-700">{t('FIELD.CALCULATED_EMPTY')}</span>}
            </output>
        </QuestionWrapper>
    );
}
