'use client';

import { useEffect, useMemo } from 'react';

import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { ClearedOptions, useClearedOptions } from '@app/store/jotai/responder-cleared-options';
import { useFormResponse, useRootFormAnswers } from '@app/store/jotai/responder-form-response';
import { useVisitedSlides } from '@app/store/jotai/responder-form-state';
import { NO_OPTION_LOGIC, OptionStates, clearUnavailableOptions, formHasOptionLogic, optionStates, optionText, selectedOptionIds } from '@app/utils/option-logic';
import { normalizeGroupAnswersForSubmit } from '@app/utils/repeating-groups';

interface Resolved {
    slides: unknown;
    answers: unknown;
    visited: unknown;
    locked: unknown;
    states: OptionStates;
}

// The last evaluation: every question of a page asks for the states, once per
// change of the answers, not once per question. Keyed by identity, so the
// answers must never be changed in place.
let last: Resolved | null = null;

/**
 * The options the questions of the form offer for these answers, decided
 * from the answers as a submission would carry them (`visited`: the pages the
 * respondent went through; a hidden group and a page off that path count as
 * unanswered), which is what the server checks. `locked`: the questions a
 * field rule sets or locks, which are not filtered. `NO_OPTION_LOGIC` for a
 * form without option logic, where nothing here applies.
 */
export function optionStatesFor(slides: StandardFormFieldDto[] | undefined, answers: Record<string, any> | undefined, visited: number[] | undefined, locked: ReadonlySet<string>): OptionStates {
    if (!formHasOptionLogic(slides)) return NO_OPTION_LOGIC;
    if (last && last.slides === slides && last.answers === answers && last.visited === visited && last.locked === locked) return last.states;
    const submitted = normalizeGroupAnswersForSubmit(slides, answers ?? {}, visited);
    const states = optionStates(slides, submitted, locked);
    last = { slides, answers, visited, locked, states };
    return states;
}

/** What the options of the question being filled in are, from the answers as they are now (see `optionStatesFor`). */
export function useOptionStates(): OptionStates {
    const form = useAppSelector(selectResponderForm);
    const answers = useRootFormAnswers();
    const visited = useVisitedSlides();
    const { locked } = useFieldRuleStates();
    return useMemo(() => optionStatesFor(form?.fields, answers, visited, locked), [form?.fields, answers, visited, locked]);
}

/**
 * The options of a question the respondent is offered, in their order, each with its
 * place among all of the question's options (a nameless one is "Item <n>"); the others
 * are not rendered. Inside a repeating-group item nothing is filtered (option logic
 * does not reach there).
 */
export function offeredChoices<T extends { id?: string }>(choices: T[] | undefined, fieldId: string, states: OptionStates, inGroup = false): Array<{ choice: T; index: number }> {
    const hidden = inGroup ? EMPTY_HIDDEN : states.hiddenOptions(fieldId);
    return (choices ?? []).map((choice, index) => ({ choice, index })).filter(({ choice }) => !choice.id || !hidden.has(choice.id));
}

const EMPTY_HIDDEN: ReadonlySet<string> = new Set();

/**
 * Keeps the respondent's answers free of options that are not available: when
 * an answer takes an option away (the earlier answer it depends on changed), a
 * selection of it is cleared and the question says so (`OptionClearedNotice`),
 * from the answers as a submission would carry them, as the server checks
 * (backend services/option_logic.py: it refuses such an answer; it never
 * deletes one). Use once on the page, outside a repeating-group item. A form
 * without option logic takes no part.
 */
export function useClearUnavailableOptions(slides: StandardFormFieldDto[] | undefined) {
    const { formResponse, setFormResponse } = useFormResponse();
    const { setCleared } = useClearedOptions();
    const visited = useVisitedSlides();
    const { locked } = useFieldRuleStates();
    const answers = formResponse.answers;
    const hasLogic = formHasOptionLogic(slides);
    // By content, not identity: a setter that changed the answers in place keeps the same object.
    const signature = hasLogic ? JSON.stringify(answers ?? {}) : '';

    useEffect(() => {
        if (!hasLogic) return;
        const submitted = (current: Record<string, any>) => normalizeGroupAnswersForSubmit(slides, current, visited);
        const fieldsById = new Map<string, StandardFormFieldDto>();
        (slides ?? []).forEach((slide) => (slide?.properties?.fields ?? []).forEach((field) => fieldsById.set(field.id, field)));
        const current = answers ?? {};
        const { answers: after, cleared } = clearUnavailableOptions(slides, current, locked, submitted);
        const selection = (source: Record<string, any>, id: string) => {
            const field = fieldsById.get(id);
            return field ? selectedOptionIds(source[id], field).join('\u0000') : '';
        };
        // A notice stays while the question's selection is what the clear left;
        // the respondent choosing again (or otherwise) takes it away.
        setCleared((was) => {
            const next: ClearedOptions = {};
            Object.entries(was).forEach(([id, entry]) => {
                if (selection(current, id) === entry.after) next[id] = entry;
            });
            cleared.forEach(({ fieldId, optionIds }) => {
                const field = fieldsById.get(fieldId);
                if (!field) return;
                const texts = [...new Set([...(next[fieldId]?.texts ?? []), ...optionIds.map((option) => optionText(field, option))])];
                next[fieldId] = { texts, after: selection(after, fieldId) };
            });
            const same = Object.keys(next).length === Object.keys(was).length && Object.entries(next).every(([id, entry]) => was[id]?.after === entry.after && was[id]?.texts.join('\u0000') === entry.texts.join('\u0000'));
            return same ? was : next;
        });
        if (!cleared.length) return;
        setFormResponse((previous) => {
            const result = clearUnavailableOptions(slides, previous.answers ?? {}, locked, submitted);
            return result.answers === previous.answers ? previous : { ...previous, answers: result.answers as typeof previous.answers };
        });
    }, [signature, slides, visited, locked, hasLogic]);
}
