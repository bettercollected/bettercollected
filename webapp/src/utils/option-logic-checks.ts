import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

/**
 * The structure of choice-level logic, apart from its evaluation
 * (utils/option-logic.ts): which questions carry it, the size caps, what a
 * save refuses and repairs, and the warnings the builder shows. Kept free of
 * the logic evaluator so that the builder's structural edits
 * (`pruneOrphanedConditions` in utils/conditional-logic.ts) can repair option
 * logic with the conditions, without a cycle. Backend twin:
 * services/option_logic.py.
 */

export const OPTION_CONDITIONS_MAX = 20; // conditions read on one option
export const OPTION_LOGIC_OPTIONS_MAX = 200; // options read on a question with option logic
export const FORM_OPTION_CONDITIONS_MAX = 1000; // option conditions read in a form
export const FORM_OPTION_FILTERS_MAX = 50; // option filters read in a form
export const OPTION_FILTER_PAIRS_MAX = 2000; // (when, show) pairs read in one filter
/** What one response may spend on option conditions, in units of work (server OPTION_LOGIC_COST_PER_RESPONSE). */
export const OPTION_LOGIC_COST_PER_RESPONSE = 500_000;
const GROUP_ITEMS_MAX = 50;

/** One row of an option filter: while the earlier question's option `when` is chosen, `show` are offered. */
export interface OptionFilterEntry {
    when: string;
    show: string[];
}

/** Filters a choice question's options by an earlier choice question's answer. */
export interface OptionFilter {
    fieldId: string;
    mapping: OptionFilterEntry[];
}

export const CHOICE_TYPES = new Set<string>([FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN]);
const GROUP_MODES = new Set(['COUNT', 'ANY', 'ALL']);

export const hasOptionLogicOn = (field: StandardFormFieldDto | undefined): boolean => !!field?.properties?.optionFilter || (field?.properties?.choices ?? []).some((choice) => choiceLogic(choice) !== null);

/** An option's logic when it is usable (an action and conditions). */
export function choiceLogic(choice: { logic?: { action?: string; conditions?: unknown[] } } | undefined) {
    const logic = choice?.logic;
    return logic && logic.action && Array.isArray(logic.conditions) && logic.conditions.length > 0 ? logic : null;
}

/** Page-level questions in form order (a group counts as one). */
export function pageQuestions(slides: StandardFormFieldDto[] | undefined): StandardFormFieldDto[] {
    const found: StandardFormFieldDto[] = [];
    (slides ?? []).forEach((slide) => found.push(...(slide?.properties?.fields ?? [])));
    return found;
}

export const isOptionTarget = (field: StandardFormFieldDto): boolean => CHOICE_TYPES.has(field?.type) && !field?.internal;

const formCache = new WeakMap<object, boolean>();

/** Does any question of the form carry option logic or a filter? Worked out once per form, so a form without any costs nothing per render. */
export function formHasOptionLogic(slides: StandardFormFieldDto[] | undefined): boolean {
    if (!slides) return false;
    let found = formCache.get(slides);
    if (found === undefined) {
        found = pageQuestions(slides).some((field) => hasOptionLogicOn(field) || (field?.type === FieldTypes.GROUP && (field.properties?.fields ?? []).some(hasOptionLogicOn)));
        formCache.set(slides, found);
    }
    return found;
}

// ---------------------------------------------------------------------------
// Warnings (the builder shows them; the server's twin is option_logic_warnings)
// ---------------------------------------------------------------------------

export type OptionLogicWarningCode = 'unreachable_option' | 'source_option_unmapped' | 'can_end_empty' | 'too_many_options';

export interface OptionLogicWarning {
    fieldId: string;
    code: OptionLogicWarningCode;
    optionId?: string;
}

/**
 * What a creator should look at, without being refused: an option no row of
 * the filter shows (`unreachable_option`), an option of the earlier question
 * with no row (`source_option_unmapped`), and a required question whose every
 * option has its own logic, so some answers leave nothing to choose (`can_end_empty`: it is then not required).
 */
export function optionLogicWarnings(slides: StandardFormFieldDto[] | undefined): OptionLogicWarning[] {
    const found: OptionLogicWarning[] = [];
    const questions = pageQuestions(slides);
    const byId = new Map(questions.filter((field) => field?.id).map((field) => [field.id, field] as const));
    questions.forEach((field) => {
        if (!isOptionTarget(field) || !hasOptionLogicOn(field)) return;
        if ((field.properties?.choices ?? []).length > OPTION_LOGIC_OPTIONS_MAX) {
            // a save is refused (the logic is never dropped unseen)
            found.push({ fieldId: field.id, code: 'too_many_options' });
            return;
        }
        const filter = field.properties?.optionFilter;
        const source = filter ? byId.get(filter.fieldId) : undefined;
        if (filter && source) {
            const shown = new Set<string>();
            const mapped = new Set<string>();
            (filter.mapping ?? []).forEach((entry) => {
                const show = (entry.show ?? []).map(String);
                if (show.length > 0) mapped.add(String(entry.when));
                show.forEach((option) => shown.add(option));
            });
            (field.properties?.choices ?? []).forEach((choice) => {
                if (choice?.id && !shown.has(choice.id)) found.push({ fieldId: field.id, code: 'unreachable_option', optionId: choice.id });
            });
            (source.properties?.choices ?? []).forEach((choice) => {
                if (choice?.id && !mapped.has(choice.id)) found.push({ fieldId: field.id, code: 'source_option_unmapped', optionId: choice.id });
            });
        }
        const choices = (field.properties?.choices ?? []).filter((choice) => choice?.id);
        if (field.validations?.required && choices.length > 0 && !field.properties?.allowOtherChoice && choices.every((choice) => choiceLogic(choice) !== null)) {
            found.push({ fieldId: field.id, code: 'can_end_empty' });
        }
    });
    return found;
}

// ---------------------------------------------------------------------------
// Saving: problems and repair (twin of the server's `_Check`)
// ---------------------------------------------------------------------------

/** A problem with a question's option logic; `optionId`: the option whose conditions it concerns, `inFilter`: the filter's. */
export interface OptionLogicProblem {
    fieldId: string;
    message: string;
    optionId?: string;
    inFilter?: boolean;
}

const PROBLEMS_MAX = 50;

const titleOf = (field: StandardFormFieldDto): string => {
    const title = field?.title;
    return typeof title === 'string' && title.trim() ? title.trim() : String(field?.id);
};

const labelOf = (choice: { id?: string; value?: string; label?: string }): string => {
    for (const text of [choice?.value, choice?.label, choice?.id]) if (typeof text === 'string' && text.trim()) return text.trim();
    return 'an option';
};

/**
 * One pass over a form's option logic: what a save would refuse. With `fix`,
 * also repair it in place (drop the condition, filter, filter entry or logic
 * that breaks a rule). `caps` hold the form's size caps, which are refused,
 * never repaired.
 */
export function checkOptionLogic(slides: StandardFormFieldDto[] | undefined, fix = false): { problems: OptionLogicProblem[]; caps: string[]; repaired: number } {
    const problems: OptionLogicProblem[] = [];
    const caps: string[] = [];
    let repaired = 0;
    const questions = pageQuestions(slides);
    // the order of the page-level questions: what "earlier" means
    const position = new Map<string, number>();
    const byId = new Map<string, StandardFormFieldDto>();
    const inGroup = new Set<string>();
    questions.forEach((field, index) => {
        if (!field?.id) return;
        position.set(field.id, index);
        byId.set(field.id, field);
        if (field.type === FieldTypes.GROUP) {
            (field.properties?.fields ?? []).forEach((child) => {
                if (!child?.id) return;
                if (!byId.has(child.id)) byId.set(child.id, child);
                inGroup.add(child.id);
            });
        }
    });
    const earlier = (sourceId: string, ownerId: string) => (position.get(sourceId) ?? Infinity) < (position.get(ownerId) ?? -1);
    const problem = (field: StandardFormFieldDto, message: string, choice?: { id?: string }, inFilter = false) => {
        if (problems.length < PROBLEMS_MAX) problems.push({ fieldId: String(field.id), message, ...(choice ? { optionId: String(choice.id) } : {}), ...(inFilter ? { inFilter: true } : {}) });
    };
    const fixed = () => {
        if (fix) repaired += 1;
    };

    const conditionProblem = (owner: StandardFormFieldDto, condition: any): string | null => {
        const sourceId = condition?.fieldId;
        if (!sourceId) return 'A condition needs a question to read.';
        if (!condition?.comparison) return 'A condition needs a comparison.';
        if (sourceId === owner.id) return 'An option cannot depend on the answer to its own question.';
        const source = byId.get(sourceId);
        if (!source) return `'${sourceId}' is not a question of this form.`;
        if (source.internal) return `'${titleOf(source)}' is an internal field: respondents never answer it, so an option cannot depend on it.`;
        if (inGroup.has(sourceId)) return `'${titleOf(source)}' is asked once per item of a repeating group. An option reads the group itself with groupMode COUNT, ANY or ALL.`;
        const isGroup = source.type === FieldTypes.GROUP;
        const mode = condition.groupMode;
        if (isGroup && !GROUP_MODES.has(mode)) return `'${titleOf(source)}' is a repeating group: set groupMode to COUNT, ANY or ALL.`;
        if (!isGroup && mode) return `groupMode only applies to repeating groups, not '${titleOf(source)}'.`;
        if (isGroup && (mode === 'ANY' || mode === 'ALL') && !(source.properties?.fields ?? []).some((child) => child.id === condition.childFieldId)) return `ANY/ALL conditions need childFieldId: a question of '${titleOf(source)}'.`;
        if (!earlier(sourceId, owner.id)) return `An option can only depend on an earlier question: '${titleOf(source)}' comes after '${titleOf(owner)}'.`;
        return null;
    };

    const checkChoiceLogic = (owner: StandardFormFieldDto, choice: any) => {
        const logic = choice.logic;
        if (logic === undefined || logic === null) return;
        const conditions: any[] = Array.isArray(logic.conditions) ? logic.conditions : [];
        const what = `The option '${labelOf(choice)}' of '${titleOf(owner)}'`;
        if (logic.action !== 'SHOW' && logic.action !== 'HIDE') {
            problem(owner, `${what} needs an action: SHOW or HIDE.`, choice);
            if (fix) {
                delete choice.logic;
                repaired += 1;
            }
            return;
        }
        if (conditions.length === 0) {
            problem(owner, `${what} has logic without conditions.`, choice);
            if (fix) {
                delete choice.logic;
                repaired += 1;
            }
            return;
        }
        const kept: any[] = [];
        conditions.forEach((condition) => {
            const found = conditionProblem(owner, condition);
            if (found === null) {
                kept.push(condition);
                return;
            }
            problem(owner, `${what}: ${found}`, choice);
            fixed();
        });
        if (fix && kept.length !== conditions.length) {
            if (kept.length) choice.logic = { ...logic, conditions: kept };
            else delete choice.logic;
        }
    };

    const checkFilter = (owner: StandardFormFieldDto) => {
        const filter = owner.properties?.optionFilter;
        if (!filter) return;
        const what = `The option filter of '${titleOf(owner)}'`;
        const sourceId = String(filter.fieldId ?? '');
        const source = byId.get(sourceId);
        let found: string | null = null;
        if (sourceId === owner.id) found = 'cannot read its own question.';
        else if (!source) found = `reads '${sourceId}', which is not a question of this form.`;
        else if (source.internal || inGroup.has(sourceId)) found = `cannot read '${titleOf(source)}': an internal question or one of a repeating group.`;
        else if (!CHOICE_TYPES.has(source.type)) found = `reads '${titleOf(source)}', which is not a single or multiple choice or dropdown question.`;
        else if (!earlier(sourceId, owner.id)) found = `can only read an earlier question: '${titleOf(source)}' comes after '${titleOf(owner)}'.`;
        if (found !== null || !source) {
            problem(owner, `${what} ${found}`, undefined, true);
            if (fix) {
                delete owner.properties!.optionFilter;
                repaired += 1;
            }
            return;
        }
        const sourceIds = new Set((source.properties?.choices ?? []).map((choice) => choice.id).filter(Boolean));
        const ownIds = new Set((owner.properties?.choices ?? []).map((choice) => choice.id).filter(Boolean));
        const mapping = filter.mapping ?? [];
        const kept: OptionFilterEntry[] = [];
        mapping.forEach((entry) => {
            if (!sourceIds.has(entry.when)) {
                problem(owner, `${what}: '${entry.when}' is not an option of '${titleOf(source)}'.`, undefined, true);
                fixed();
                return;
            }
            const show = entry.show ?? [];
            const good = show.filter((option) => ownIds.has(option));
            if (good.length !== show.length) {
                problem(owner, `${what}: an entry names an option that '${titleOf(owner)}' does not have.`, undefined, true);
                fixed();
                kept.push({ ...entry, show: fix ? good : show });
                return;
            }
            kept.push(entry);
        });
        if (fix) {
            if (kept.length === 0) delete owner.properties!.optionFilter;
            else if (kept.length !== mapping.length || kept.some((entry, i) => entry !== mapping[i])) owner.properties!.optionFilter = { ...filter, mapping: kept };
        }
    };

    const whole = (question: StandardFormFieldDto, message: string) => {
        problem(question, message);
        if (!fix) return;
        (question.properties?.choices ?? []).forEach((choice) => {
            if (choice.logic !== undefined) delete choice.logic;
        });
        if (question.properties?.optionFilter) delete question.properties.optionFilter;
        repaired += 1;
    };

    let conditionCount = 0;
    let filterCount = 0;
    questions.forEach((field) => {
        const targets = [field, ...(field?.type === FieldTypes.GROUP ? (field.properties?.fields ?? []) : [])];
        targets.forEach((question) => {
            if (!hasOptionLogicOn(question)) return;
            if (question !== field) return whole(question, `'${titleOf(question)}' is in a repeating group: option logic is not supported there yet.`);
            if (!isOptionTarget(question)) return whole(question, `'${titleOf(question)}' is not a single or multiple choice or dropdown question (or is internal), so its options cannot have logic.`);
            if ((question.properties?.choices ?? []).length > OPTION_LOGIC_OPTIONS_MAX) {
                // never repaired away: a save that would lose the logic is refused, saying why
                caps.push(`'${titleOf(question)}' has more than ${OPTION_LOGIC_OPTIONS_MAX} options, too many for option logic: remove its option logic or some of its options.`);
                return;
            }
            (question.properties?.choices ?? []).forEach((choice) => checkChoiceLogic(question, choice));
            checkFilter(question);
            conditionCount += (question.properties?.choices ?? []).reduce((sum, choice) => sum + (Array.isArray(choice.logic?.conditions) ? choice.logic!.conditions.length : 0), 0);
            filterCount += question.properties?.optionFilter ? 1 : 0;
        });
    });
    if (conditionCount > FORM_OPTION_CONDITIONS_MAX) caps.push(`A form can have at most ${FORM_OPTION_CONDITIONS_MAX} option conditions; this one has ${conditionCount}.`);
    if (filterCount > FORM_OPTION_FILTERS_MAX) caps.push(`A form can have at most ${FORM_OPTION_FILTERS_MAX} option filters; this one has ${filterCount}.`);
    if (conditionCount > 0 && caps.length === 0 && worstCaseCost(slides) > OPTION_LOGIC_COST_PER_RESPONSE) {
        caps.push("This form's option logic is too costly to check for each response (many conditions on questions with many options or on repeating groups): use fewer conditions.");
    }
    return { problems, caps, repaired };
}

/**
 * The most a response can spend on the form's option conditions, in the units
 * of the server's budget (backend `worst_case_cost`): every option of a
 * question a condition reads chosen, every group it reads at 50 items with
 * every option chosen in each.
 */
export function worstCaseCost(slides: StandardFormFieldDto[] | undefined): number {
    const questions = pageQuestions(slides);
    const byId = new Map<string, StandardFormFieldDto>();
    questions.forEach((question) => {
        if (question?.id) byId.set(question.id, question);
        if (question?.type === FieldTypes.GROUP) (question.properties?.fields ?? []).forEach((child) => child?.id && !byId.has(child.id) && byId.set(child.id, child));
    });
    let total = 0;
    questions.forEach((question) => {
        (question.properties?.choices ?? []).forEach((choice) => {
            const logic = choiceLogic(choice);
            ((logic?.conditions as any[]) ?? []).slice(0, OPTION_CONDITIONS_MAX).forEach((condition) => {
                total += 1;
                const source = byId.get(condition?.fieldId ?? '');
                if (!source || condition.groupMode === 'COUNT') return;
                if (condition.groupMode === 'ANY' || condition.groupMode === 'ALL') {
                    const child = byId.get(condition.childFieldId ?? '');
                    total += GROUP_ITEMS_MAX * (1 + (child && CHOICE_TYPES.has(child.type) ? (child.properties?.choices ?? []).length : 0));
                } else if (CHOICE_TYPES.has(source.type)) total += (source.properties?.choices ?? []).length;
            });
        });
    });
    return total;
}

/** What a save of the form would refuse (messages), for the questions that carry option logic; not repaired. */
export function optionLogicProblems(slides: StandardFormFieldDto[] | undefined): OptionLogicProblem[] {
    if (!formHasOptionLogic(slides)) return [];
    const { problems, caps } = checkOptionLogic(slides, false);
    return [...problems, ...caps.map((message) => ({ fieldId: '', message }))].slice(0, PROBLEMS_MAX);
}

/**
 * Repair the form's option logic in place after a structural edit (a removed
 * or moved question, a removed option, a question made internal or of another
 * type): drop the conditions that read something that is gone, is internal, is
 * the question itself, is asked later or is in a repeating group, the filter
 * that reads such a question, and the filter entries that name options that
 * are gone. Twin of the server's `prune_option_logic`. Returns how many
 * pieces were dropped.
 */
export function pruneOptionLogic(slides: StandardFormFieldDto[]): number {
    return checkOptionLogic(slides, true).repaired;
}
