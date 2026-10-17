'use client';

import { useEffect } from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { getCalculatedFields, localToday, withCalculatedAnswers } from '@app/utils/calculated-fields';

/**
 * Keeps the respondent's calculated answers in step with their other
 * answers: whenever an answer changes, every calculated field is recomputed
 * (in dependency order) and written into the form's answers, so conditional
 * logic, page jumps, piping and the calculated fields themselves read the
 * current value. The write settles at once: recomputing from the new answers
 * gives the same values. Use outside a repeating-group item.
 *
 * What is submitted for these fields is never trusted: the server recomputes
 * them (backend services/calculated_fields.py).
 */
export function useCalculatedFields(slides: StandardFormFieldDto[] | undefined) {
    const { formResponse, setFormResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    const answers = formResponse.answers;
    const hasCalculations = getCalculatedFields(slides).length > 0;
    // By content, not identity: some setters change the answers in place
    // (removeAnswer), which keeps the same object.
    const signature = hasCalculations ? JSON.stringify(answers ?? {}) : '';

    useEffect(() => {
        if (!hasCalculations) return;
        const today = localToday();
        const current = answers ?? {};
        if (withCalculatedAnswers(slides, current, hiddenValues, today) === current) return;
        setFormResponse((previous) => {
            const next = withCalculatedAnswers(slides, previous.answers ?? {}, hiddenValues, today);
            return next === previous.answers ? previous : { ...previous, answers: next as typeof previous.answers };
        });
    }, [signature, hiddenValues, slides, hasCalculations]);
}
