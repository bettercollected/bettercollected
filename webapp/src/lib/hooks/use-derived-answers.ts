'use client';

import { useEffect, useRef } from 'react';

import { withDerivedAnswers } from '@app/lib/field-rules';
import { hasFieldRules } from '@app/lib/hooks/use-field-rule-states';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useVisitedSlides } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { getCalculatedFields, localToday, withCalculatedAnswers } from '@app/utils/calculated-fields';
import { normalizeGroupAnswersForSubmit } from '@app/utils/repeating-groups';

/** Writes of the derived answers in a row, none of them the respondent's doing, after which the hook stops: a form whose values never settle must not freeze the page. */
export const DERIVED_WRITES_MAX = 20;

/**
 * Keeps the answers the form owns in step with the respondent's others:
 * whenever an answer changes, every calculated field is recomputed and, in
 * the same dependency order, each question a field rule sets or locks (a
 * locked question the respondent had already answered loses that answer),
 * and the results are written into the form's answers, so conditional logic,
 * page jumps, answer piping and the rules themselves read the current
 * values. The write settles at once: recomputing from the new answers gives
 * the same values (a value in a circle has none), and a guard stops it
 * after DERIVED_WRITES_MAX writes in a row that no answer of the respondent
 * caused. The values are worked out from the answers as a submission would
 * carry them (a hidden group and a page off the visited path are left out),
 * as the server replays them. Use outside a repeating-group item.
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
    const visited = useVisitedSlides();
    const hasRules = hasFieldRules(slides);
    const hasCalculations = getCalculatedFields(slides).length > 0;
    // By content, not identity (a setter that changes the answers in place
    // keeps the same object; none should, but a stale form is worse than a
    // stringify).
    const signature = hasRules || hasCalculations ? JSON.stringify(answers ?? {}) : '';
    // Our own writes, to tell them from the respondent's changes.
    const written = useRef({ signature: '', count: 0 });

    useEffect(() => {
        if (!hasRules && !hasCalculations) return;
        const today = localToday();
        const submitted = (current: Record<string, any>) => normalizeGroupAnswersForSubmit(slides, current, visited);
        const derive = (current: Record<string, any>) => (hasRules ? withDerivedAnswers(slides, current, hiddenValues, today, hiddenNames ?? [], submitted).answers : withCalculatedAnswers(slides, current, hiddenValues, today));
        const current = answers ?? {};
        const next = derive(current);
        if (next === current) {
            written.current.count = 0;
            return;
        }
        // The answers are the ones this hook wrote last: another round of its own.
        written.current.count = signature === written.current.signature ? written.current.count + 1 : 0;
        if (written.current.count >= DERIVED_WRITES_MAX) return;
        written.current.signature = JSON.stringify(next);
        setFormResponse((previous) => {
            const result = derive(previous.answers ?? {});
            return result === previous.answers ? previous : { ...previous, answers: result as typeof previous.answers };
        });
    }, [signature, hiddenValues, slides, hasRules, hasCalculations, visited]);
}
