'use client';

import { useMemo } from 'react';

import { FieldRuleStates, NO_RULES, formHasFieldRules, resolveFieldRules } from '@app/lib/field-rules';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useRootFormAnswers } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { localToday } from '@app/utils/calculated-fields';

const hasRulesBySlides = new WeakMap<object, boolean>();

/** Does the form carry field rules? Worked out once per form, so a form without any costs nothing per render. */
export function hasFieldRules(slides: StandardFormFieldDto[] | undefined): boolean {
    if (!slides) return false;
    let found = hasRulesBySlides.get(slides);
    if (found === undefined) {
        found = formHasFieldRules(slides);
        hasRulesBySlides.set(slides, found);
    }
    return found;
}

interface Resolved {
    slides: unknown;
    answers: unknown;
    hiddenValues: unknown;
    names: unknown;
    today: string;
    states: FieldRuleStates;
}

// The last evaluation: every question of a page asks for the states, once per
// change of the answers, not once per question.
let last: Resolved | null = null;

/** The states field rules give the questions of the form for these answers (shared by all callers with the same inputs). */
export function statesFor(slides: StandardFormFieldDto[] | undefined, answers: Record<string, any> | undefined, hiddenValues: Record<string, string>, names: string[] | undefined): FieldRuleStates {
    if (!hasFieldRules(slides)) return NO_RULES;
    const today = localToday();
    if (last && last.slides === slides && last.answers === answers && last.hiddenValues === hiddenValues && last.names === names && last.today === today) return last.states;
    const states = resolveFieldRules(slides, answers, hiddenValues, today, names ?? []).states;
    last = { slides, answers, hiddenValues, names, today, states };
    return states;
}

/**
 * What field rules decide for the question being filled in, from the answers
 * as they are now: required or optional, locked (read-only or set by the
 * form) and the texts a rule changed. `NO_RULES` for a form without rules,
 * where nothing here applies. The answers themselves are written by
 * `useDerivedAnswers` (the page does that once); this only reads.
 */
export function useFieldRuleStates(): FieldRuleStates {
    const form = useAppSelector(selectResponderForm);
    const answers = useRootFormAnswers();
    const { hiddenValues } = useHiddenFieldValues();
    return useMemo(() => statesFor(form?.fields, answers, hiddenValues, form?.hiddenFields), [form?.fields, answers, hiddenValues, form?.hiddenFields]);
}
