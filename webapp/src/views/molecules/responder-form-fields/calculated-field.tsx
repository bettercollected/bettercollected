import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { calculatedAnswerValue, fieldTitleText, formatCalculatedValue, usesAnyAnswer } from '@app/utils/calculated-fields';

import QuestionWrapper from './question-wrapper';

/**
 * A calculated value as respondents see it: the field's label and the value
 * computed from their answers so far, read-only, formatted per the field's
 * format in the form's language. The value is a polite live region labelled
 * by the field's title, so a screen reader announces it when it changes.
 * Fields hidden from respondents never get here (form-slide.tsx).
 *
 * The value shows once the respondent has given an answer the formula uses
 * (directly or through other calculations): before that, "Not calculated
 * yet", rather than a total of 0 or a score of 0%. The value itself is
 * still computed (and stored by the server) all along.
 */
export default function CalculatedField({ field, slides }: { field: StandardFormFieldDto; slides?: StandardFormFieldDto[] }) {
    const { formResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    const responderForm = useAppSelector(selectResponderForm);
    const formSlides = slides ?? responderForm?.fields;
    const { theme } = useFormState();
    const { t, language } = useRespondentLanguage();
    // An untitled calculation shows no title: its value is still named.
    const titled = !!fieldTitleText(field);
    const answered = usesAnyAnswer(field, formSlides, formResponse.answers ?? {}, hiddenValues);
    const value = answered ? calculatedAnswerValue(formResponse.answers?.[field.id]) : null;
    const text = typeof value === 'boolean' ? t(value ? 'FIELD.CALCULATED_TRUE' : 'FIELD.CALCULATED_FALSE') : formatCalculatedValue(value, field.properties?.format, language);

    return (
        <QuestionWrapper field={field}>
            <output
                id={`calculated-${field.id}`}
                aria-live="polite"
                aria-atomic="true"
                aria-labelledby={titled ? `q-title-${field.id} calculated-${field.id}` : undefined}
                aria-label={titled ? undefined : t('FIELD.CALCULATION')}
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
