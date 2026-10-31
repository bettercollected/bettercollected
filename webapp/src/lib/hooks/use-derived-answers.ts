'use client';

import { useEffect } from 'react';

import { withDerivedAnswers } from '@app/lib/field-rules';
import { hasFieldRules } from '@app/lib/hooks/use-field-rule-states';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { getCalculatedFields, localToday, withCalculatedAnswers } from '@app/utils/calculated-fields';

/**
 * Keeps the answers the form owns in step with the respondent's others:
 * whenever an answer changes, every calculated field is recomputed and, in
 * the same dependency order, each question a field rule sets or locks (a
 * locked question the respondent had already answered loses that answer),
 * and the results are written into the form's answers, so conditional logic,
 * page jumps, answer piping and the rules themselves read the current
 * values. The write settles at once: recomputing from the new answers gives
 * the same values. Use outside a repeating-group item.
 *
 * What is submitted for these questions is never trusted: the server
 * recomputes them (backend services/calculated_fields.py and
 * services/field_rules.py). A form without field rules takes the path it
 * always had (calculated fields only).
 *
 * `hiddenNames`: the form's declared hidden fields (a rule may read one the
 * link did not fill).
 */
export function useDerivedAnswers(slides: StandardFormFieldDto[] | undefined, hiddenNames?: string[]) {
    const { formResponse, setFormResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    const answers = formResponse.answers;
    const hasRules = hasFieldRules(slides);
    const hasCalculations = getCalculatedFields(slides).length > 0;
    // By content, not identity: some setters change the answers in place
    // (removeAnswer), which keeps the same object.
    const signature = hasRules || hasCalculations ? JSON.stringify(answers ?? {}) : '';

    useEffect(() => {
        if (!hasRules && !hasCalculations) return;
        const today = localToday();
        const derive = (current: Record<string, any>) => (hasRules ? withDerivedAnswers(slides, current, hiddenValues, today, hiddenNames ?? []).answers : withCalculatedAnswers(slides, current, hiddenValues, today));
        const current = answers ?? {};
        if (derive(current) === current) return;
        setFormResponse((previous) => {
            const next = derive(previous.answers ?? {});
            return next === previous.answers ? previous : { ...previous, answers: next as typeof previous.answers };
        });
    }, [signature, hiddenValues, slides, hasRules, hasCalculations]);
}
