import { StandardFormFieldDto } from '@app/models/dtos/form';
import { LogicSources, evaluateConditions, logicSourcesById } from '@app/utils/conditional-logic';
import {
    CHOICE_TYPES,
    FORM_OPTION_CONDITIONS_MAX,
    FORM_OPTION_FILTERS_MAX,
    OPTION_CONDITIONS_MAX,
    OPTION_FILTER_PAIRS_MAX,
    OPTION_LOGIC_OPTIONS_MAX,
    OptionFilter,
    choiceLogic,
    formHasOptionLogic,
    hasOptionLogicOn,
    isOptionTarget,
    pageQuestions
} from '@app/utils/option-logic-checks';

// The structure of option logic (caps, save checks, repair, warnings) lives in
// utils/option-logic-checks.ts, free of this evaluator; both are the one API.
export * from '@app/utils/option-logic-checks';

/**
 * Choice-level logic: which options of a choice question respondents are
 * offered. A choice question (single or multiple choice, dropdown) may
 *
 *  - give an option its own `logic` (`choices[].logic`, the question-level
 *    `FieldConditionalLogic`: SHOW = offered only while the conditions hold,
 *    HIDE = offered unless they hold), and
 *  - filter its options by an earlier choice question's answer
 *    (`properties.optionFilter`): the options offered are those the chosen
 *    options of that question map to (the union over a multiple choice's
 *    selection). Without an answer to it (or with only "Other" text)
 *    nothing is filtered; a chosen option with no row offers nothing.
 *
 * An option is available when its own logic allows it and the filter lets
 * it through. Pure TypeScript twin of backend services/option_logic.py; the
 * shared cases in docs/spec/option-logic.cases.json run on both sides, so
 * change one evaluator only together with the other. The server is the
 * authority: an answer that selects an option that is not available is
 * refused (`hidden_option`). The respondent page clears such a selection
 * itself (`clearUnavailableOptions`) and says so politely.
 *
 *  - A question with nothing available (and no "Other") is never required,
 *    and `minChoices` is held to what is available. A question a field rule
 *    sets or locks is not filtered.
 *  - Like `logic`, conditions read the answers as given, hidden or not. A
 *    condition or filter that reads something the form does not have (a
 *    removed question, an internal one, the question itself) is not active:
 *    the option is offered.
 */

type Answers = Record<string, any>;

/** The option ids an answer to a choice question selects: de-duplicated, only options the question has ("Other" text is not an option). */
export function selectedOptionIds(answer: any, field: StandardFormFieldDto | undefined): string[] {
    if (!answer || typeof answer !== 'object') return [];
    const known = new Set((field?.properties?.choices ?? []).map((choice) => choice?.id).filter((id): id is string => typeof id === 'string' && id !== ''));
    const values: unknown[] = [];
    const many = answer.choices;
    if (many && typeof many === 'object' && Array.isArray(many.values)) values.push(...many.values);
    const one = answer.choice;
    if (one && typeof one === 'object' && one.value !== undefined && one.value !== null && one.value !== '') values.push(one.value);
    const picked: string[] = [];
    const seen = new Set<string>();
    values.forEach((value) => {
        if (typeof value === 'string' && known.has(value) && !seen.has(value)) {
            seen.add(value);
            picked.push(value);
        }
    });
    return picked;
}

/** What the options of the form's questions are for one set of answers. */
export class OptionStates {
    constructor(
        /** question id -> option ids not available */
        readonly hidden: Map<string, Set<string>> = new Map(),
        /** questions with no available option and no "Other" (never required) */
        readonly noneLeft: Set<string> = new Set(),
        /** question id -> how many options it offers (with "Other"), where it has logic */
        readonly offered: Map<string, number> = new Map()
    ) {}

    hiddenOptions(fieldId: string): Set<string> {
        return this.hidden.get(fieldId) ?? EMPTY;
    }

    isNoneLeft(fieldId: string): boolean {
        return this.noneLeft.has(fieldId);
    }

    /** `minChoices` held to what the question offers. */
    minChoices(fieldId: string, staticMin: number | undefined): number | undefined {
        const offered = this.offered.get(fieldId);
        return staticMin === undefined || offered === undefined ? staticMin : Math.min(staticMin, offered);
    }
}

const EMPTY: Set<string> = new Set();
export const NO_OPTION_LOGIC = new OptionStates();

const isDangling = (conditions: Array<{ fieldId?: string; groupMode?: string; childFieldId?: string }>, owner: string, sources: LogicSources): boolean =>
    conditions.some((condition) => {
        const source = condition?.fieldId ?? '';
        if (!source || source === owner || !(source in sources)) return true;
        if ((condition.groupMode === 'ANY' || condition.groupMode === 'ALL') && (!condition.childFieldId || !(condition.childFieldId in sources))) return true;
        return false;
    });

/** The option ids a filter lets through; undefined when it filters nothing (its source is gone, is no choice question, or has no selected option). */
function allowedByFilter(filter: OptionFilter, owner: string, answers: Answers, sources: LogicSources): Set<string> | undefined {
    const source = sources[filter.fieldId ?? ''];
    if (!source || filter.fieldId === owner || !CHOICE_TYPES.has(source.type)) return undefined;
    const selected = new Set(selectedOptionIds(answers[filter.fieldId], source));
    if (selected.size === 0) return undefined;
    const allowed = new Set<string>();
    (filter.mapping ?? []).slice(0, OPTION_FILTER_PAIRS_MAX).forEach((entry) => {
        if (selected.has(entry?.when)) (entry.show ?? []).slice(0, OPTION_FILTER_PAIRS_MAX).forEach((option) => allowed.add(String(option)));
    });
    return allowed;
}

function questionState(field: StandardFormFieldDto, answers: Answers, sources: LogicSources, budget: { conditions: number; filters: number }): { hidden: Set<string>; offered: number } {
    const owner = field.id;
    const choices = (field.properties?.choices ?? []).slice(0, OPTION_LOGIC_OPTIONS_MAX);
    const filter = field.properties?.optionFilter;
    let allowed: Set<string> | undefined;
    if (filter) {
        if (budget.filters > 0) {
            budget.filters -= 1;
            allowed = allowedByFilter(filter, owner, answers, sources);
        }
    }
    const hidden = new Set<string>();
    choices.forEach((choice) => {
        if (!choice?.id) return;
        if (allowed && !allowed.has(choice.id)) {
            hidden.add(choice.id);
            return;
        }
        const logic = choiceLogic(choice);
        if (!logic) return;
        const conditions = (logic.conditions as any[]).slice(0, OPTION_CONDITIONS_MAX);
        if (conditions.length > budget.conditions) return;
        budget.conditions -= conditions.length;
        if (isDangling(conditions, owner, sources)) return;
        const met = evaluateConditions((logic as any).operator, conditions, answers, sources);
        if ((logic.action === 'SHOW') !== met) hidden.add(choice.id);
    });
    return { hidden, offered: choices.length - hidden.size };
}

/**
 * The availability of the options of every page-level choice question that
 * has option logic, for `answers`. `slides`: the form as respondents are
 * served it (no internal questions). `locked`: questions a field rule sets
 * or locks: not filtered.
 */
export function optionStates(slides: StandardFormFieldDto[] | undefined, answers: Answers | undefined, locked?: Iterable<string>): OptionStates {
    if (!formHasOptionLogic(slides)) return NO_OPTION_LOGIC;
    const questions = pageQuestions(slides).filter((field) => isOptionTarget(field) && hasOptionLogicOn(field));
    if (questions.length === 0) return NO_OPTION_LOGIC;
    const sources = logicSourcesById(slides);
    const lockedIds = new Set(locked ?? []);
    const budget = { conditions: FORM_OPTION_CONDITIONS_MAX, filters: FORM_OPTION_FILTERS_MAX };
    const states = new OptionStates();
    const given = answers ?? {};
    questions.forEach((field) => {
        if (lockedIds.has(field.id)) return;
        const { hidden, offered } = questionState(field, given, sources, budget);
        if (hidden.size === 0) return;
        const other = !!field.properties?.allowOtherChoice;
        states.hidden.set(field.id, hidden);
        states.offered.set(field.id, offered + (other ? 1 : 0));
        if (offered <= 0 && !other) states.noneLeft.add(field.id);
    });
    return states;
}

/** Does the answer select an option the question does not offer? */
export function selectsUnavailableOption(field: StandardFormFieldDto, answer: any, states: OptionStates): boolean {
    const hidden = states.hiddenOptions(field.id);
    return hidden.size > 0 && selectedOptionIds(answer, field).some((option) => hidden.has(option));
}

/** The text of an option as the question shows it (its text, else its label, else "Item <n>"). */
export function optionText(field: StandardFormFieldDto, optionId: string): string {
    const choices = field.properties?.choices ?? [];
    const index = choices.findIndex((choice) => choice?.id === optionId);
    if (index < 0) return optionId;
    const choice = choices[index];
    return choice.value ? choice.value : choice.label ? choice.label : `Item ${index + 1}`;
}

/** A selection the respondent page cleared because its option stopped being available. */
export interface ClearedSelection {
    fieldId: string;
    optionIds: string[];
}

/** The answer without the given options (undefined when nothing else is chosen: "Other" text stays). */
function withoutOptions(answer: any, remove: Set<string>): any | undefined {
    const next = JSON.parse(JSON.stringify(answer));
    if (next?.choices && Array.isArray(next.choices.values)) {
        next.choices.values = next.choices.values.filter((value: unknown) => !(typeof value === 'string' && remove.has(value)));
        const hasOther = typeof next.choices.other === 'string' && next.choices.other !== '';
        if (next.choices.values.length === 0 && !hasOther) return undefined;
        if (next.choices.values.length === 0) delete next.choices.values;
    }
    if (next?.choice && typeof next.choice.value === 'string' && remove.has(next.choice.value)) {
        const hasOther = typeof next.choice.other === 'string' && next.choice.other !== '';
        if (!hasOther) return undefined;
        delete next.choice.value;
    }
    return next;
}

/**
 * Clear the selections of options that are not available, until none is:
 * the respondent page's reaction to an answer that took an option away.
 * Availability is worked out from the answers as a submission would carry
 * them (`submitted`: hidden groups and pages off the path left out), which
 * is what the server checks. Every question is looked at, shown or not
 * (an answer to a hidden question is cleared too, since the server would
 * refuse it were the question shown), so nothing stale reaches a
 * submission. Returns the same object when nothing changed.
 */
export function clearUnavailableOptions(slides: StandardFormFieldDto[] | undefined, answers: Answers, locked?: Iterable<string>, submitted: (current: Answers) => Answers = (current) => current): { answers: Answers; cleared: ClearedSelection[] } {
    if (!formHasOptionLogic(slides)) return { answers, cleared: [] };
    const questions = pageQuestions(slides).filter((field) => isOptionTarget(field) && hasOptionLogicOn(field));
    let current = answers;
    const cleared = new Map<string, Set<string>>();
    // each round clears at least one selection, so the rounds are bounded
    for (let round = 0; round <= questions.length; round++) {
        const states = optionStates(slides, submitted(current), locked);
        let next = current;
        questions.forEach((field) => {
            const hidden = states.hiddenOptions(field.id);
            if (hidden.size === 0) return;
            const stale = selectedOptionIds(next[field.id], field).filter((option) => hidden.has(option));
            if (stale.length === 0) return;
            next = { ...next };
            const rest = withoutOptions(next[field.id], new Set(stale));
            if (rest === undefined) delete next[field.id];
            else next[field.id] = rest;
            const was = cleared.get(field.id) ?? new Set<string>();
            stale.forEach((option) => was.add(option));
            cleared.set(field.id, was);
        });
        if (next === current) break;
        current = next;
    }
    return { answers: current, cleared: [...cleared].map(([fieldId, optionIds]) => ({ fieldId, optionIds: [...optionIds] })) };
}

// ---------------------------------------------------------------------------
// Which questions an edit puts in question
// ---------------------------------------------------------------------------

/** The question ids an option's logic and filter read. */
function reads(field: StandardFormFieldDto): Set<string> {
    const found = new Set<string>();
    const filter = field.properties?.optionFilter;
    if (filter?.fieldId) found.add(filter.fieldId);
    (field.properties?.choices ?? []).forEach((choice) => {
        (choiceLogic(choice)?.conditions as Array<{ fieldId?: string; childFieldId?: string }> | undefined)?.forEach((condition) => {
            if (condition?.fieldId) found.add(condition.fieldId);
            if (condition?.childFieldId) found.add(condition.childFieldId);
        });
    });
    return found;
}

/** Choice questions whose options read one of `keys`, through other such questions as well. */
export function optionKeysAffected(slides: StandardFormFieldDto[] | undefined, keys: Iterable<string>): Set<string> {
    const readers = new Map(
        pageQuestions(slides)
            .filter((field) => isOptionTarget(field) && hasOptionLogicOn(field))
            .map((field) => [field.id, reads(field)] as const)
    );
    const changed = new Set(keys);
    const affected = new Set<string>();
    let grew = true;
    while (grew) {
        grew = false;
        readers.forEach((read, id) => {
            if (!affected.has(id) && [...read].some((key) => changed.has(key) || affected.has(key))) {
                affected.add(id);
                grew = true;
            }
        });
    }
    return affected;
}
