import { ExprNode, ExprValue, MAX_INPUT_STRING_LENGTH, evaluateExpression, formatExpressionValue } from '@app/lib/expressions';
import { Dec } from '@app/lib/expressions/decimal';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { buildVariables, calculatedAnswer, calculationVariables, expressionVariables, getCalculatedFields, idMap, pageFields, questionKeys, readingFor } from '@app/utils/calculated-fields';
import { LogicSources, evaluateConditions, getComparableAnswerValue, getGroupAnswerItems, logicSourcesById } from '@app/utils/conditional-logic';
import { getRepeatSettings, isRepeatingGroup } from '@app/utils/repeating-groups';

/**
 * Field rules ("logic actions"): ordered rules on a question that, while
 * their `when` holds, make it required or optional, read-only, give it a
 * value or change its title or description. A rule never changes visibility
 * (`properties.logic` does).
 *
 * Pure TypeScript twin of backend services/field_rules.py: no `eval`, no
 * `Function`, only the fixed expression operators and the same caps. The
 * server is the authority (it recomputes values, discards read-only input
 * and enforces Required with the rules applied); this evaluator shows
 * respondents what the server will do. The two run the same shared cases
 * (docs/spec/answer-validation.cases.json, checks `fieldRules`, and
 * docs/spec/field-rules.cases.json), so they cannot drift unnoticed.
 *
 * - Precedence: a field's rules apply in order; for each property the last
 *   active rule wins. `required` starts from `validations.required`.
 * - Values the form owns: while a rule with `setValue` is active, the
 *   answer is that value (an empty result removes the respondent's); while
 *   a rule with `readOnly` is active and none sets a value, the
 *   respondent's answer is removed. Calculated fields and these questions
 *   are evaluated in one dependency order, each written into the answers
 *   and the variables before the next, so a trigger that reads a
 *   calculation or a set value sees the final one.
 * - Such a question is "locked": never required, and its answer rules and
 *   date rules are not the respondent's to meet.
 * - A rule that reads something the form does not have (a removed
 *   question, an unknown variable, its own question) is not active.
 */

export const FIELD_RULES_MAX = 8; // rules read on one question
export const FORM_FIELD_RULES_MAX = 100; // rules read in a whole form
/** Evaluation cost one pass may spend on rules (server RULE_COST_PER_RESPONSE). */
export const RULE_COST_PER_RESPONSE = 200_000;
// Items a group list may hold when nothing better is known.
const LIST_ITEMS_MAX = 50;

export interface FieldRuleCondition {
    fieldId?: string;
    fieldType?: string;
    comparison?: string;
    value?: unknown;
    groupMode?: string;
    childFieldId?: string;
    childFieldType?: string;
}

export interface FieldRuleTrigger {
    operator?: 'AND' | 'OR';
    conditions?: FieldRuleCondition[];
    expression?: ExprNode | unknown;
}

export interface FieldRuleEffect {
    required?: boolean;
    readOnly?: true;
    title?: string;
    description?: string;
    setValue?: { const?: boolean | number | string; expression?: ExprNode | unknown };
}

export interface FieldRule {
    id: string;
    when: FieldRuleTrigger;
    then: FieldRuleEffect;
}

type Answers = Record<string, any>;

/** Question types whose value a rule may set or lock (page questions only). */
export const VALUE_TYPES = new Set<string>([FieldTypes.SHORT_TEXT, FieldTypes.LONG_TEXT, FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN, FieldTypes.NUMBER, FieldTypes.DATE, FieldTypes.YES_NO]);
const TEXT_TYPES = new Set<string>([FieldTypes.SHORT_TEXT, FieldTypes.LONG_TEXT]);
export const CHOICE_TYPES = new Set<string>([FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN]);

export const rulesOf = (field: StandardFormFieldDto | undefined): FieldRule[] => {
    const rules = field?.properties?.rules;
    return Array.isArray(rules) ? (rules as FieldRule[]).filter((rule) => rule && typeof rule === 'object') : [];
};

/** Does any question of the form carry rules? (Forms without them take none of this module's paths.) */
export function formHasFieldRules(slides: StandardFormFieldDto[] | undefined | null): boolean {
    return targetsOf(slides).some((target) => rulesOf(target.field).length > 0);
}

export interface Target {
    field: StandardFormFieldDto;
    group?: StandardFormFieldDto;
}

/** Every question of a page-based form, a repeating group's children right after the group. */
export function targetsOf(slides: StandardFormFieldDto[] | undefined | null): Target[] {
    const found: Target[] = [];
    pageFields(slides).forEach((field) => {
        found.push({ field });
        if (isRepeatingGroup(field)) (field.properties?.fields ?? []).forEach((child) => found.push({ field: child, group: field }));
    });
    return found;
}

export const effect = (rule: FieldRule, key: keyof FieldRuleEffect): unknown => (rule.then as FieldRuleEffect | undefined)?.[key];
export const present = (value: unknown): boolean => value !== undefined && value !== null;
export const hasValueEffect = (rule: FieldRule): boolean => present(effect(rule, 'readOnly')) || present(effect(rule, 'setValue'));
export const hasStateEffect = (rule: FieldRule): boolean => ['required', 'title', 'description'].some((key) => present(effect(rule, key as keyof FieldRuleEffect)));

export const isMultiple = (field: StandardFormFieldDto): boolean => field.type === FieldTypes.MULTIPLE_CHOICE && !!field.properties?.allowMultipleSelection;

export function isValueNode(target: Target): boolean {
    return !target.group && !target.field.internal && VALUE_TYPES.has(target.field.type) && !isMultiple(target.field) && rulesOf(target.field).some(hasValueEffect);
}

export const answerKey = (key: string): string => key.split('.', 1)[0];

export function triggerReads(rule: FieldRule): string[] {
    const when = rule.when;
    if (present(when?.expression)) return expressionVariables(when.expression);
    const keys: string[] = [];
    (when?.conditions ?? []).forEach((condition) => {
        const key = condition?.fieldId;
        if (key && !keys.includes(String(key))) keys.push(String(key));
    });
    return keys;
}

export function valueReads(rule: FieldRule): string[] {
    const expression = (effect(rule, 'setValue') as FieldRuleEffect['setValue'])?.expression;
    return present(expression) ? expressionVariables(expression) : [];
}

export function ruleReads(rule: FieldRule): string[] {
    const trigger = triggerReads(rule);
    return [...trigger, ...valueReads(rule).filter((key) => !trigger.includes(key))];
}

// ---------------------------------------------------------------------------
// Cost (a response's evaluation budget, as the server counts it)
// ---------------------------------------------------------------------------

class TooCostly extends Error {}

class Budget {
    left = RULE_COST_PER_RESPONSE;
    charge(cost: number) {
        this.left -= cost;
        if (this.left < 0) throw new TooCostly();
    }
}

/** Nodes of an AST, plus the items of every group list it reads. */
function astCost(ast: unknown, groupItems: Record<string, number>): number {
    // (a loop, not `push(...value)`: an argument list has a size limit)
    let cost = 0;
    const pending: unknown[] = [ast];
    while (pending.length) {
        const node = pending.pop();
        cost += 1;
        if (!node || typeof node !== 'object' || Array.isArray(node)) continue;
        const entries = Object.entries(node as Record<string, unknown>);
        if (entries.length !== 1) continue;
        const [op, value] = entries[0];
        if (op === 'var' && typeof value === 'string' && value.includes('.')) cost += groupItems[answerKey(value)] ?? LIST_ITEMS_MAX;
        else if (Array.isArray(value)) for (const child of value) pending.push(child);
    }
    return cost;
}

/** What one evaluation of a rule (trigger and set value) costs, with every group at its maximum. */
export function ruleCost(rule: FieldRule, groupItems: Record<string, number>): number {
    const when = rule.when;
    let cost = 0;
    if (present(when?.expression)) cost += astCost(when.expression, groupItems);
    (when?.conditions ?? []).forEach((condition) => {
        cost += 1;
        if (condition?.groupMode === 'ANY' || condition?.groupMode === 'ALL') cost += groupItems[String(condition.fieldId ?? '')] ?? LIST_ITEMS_MAX;
    });
    const expression = (effect(rule, 'setValue') as FieldRuleEffect['setValue'])?.expression;
    if (present(expression)) cost += astCost(expression, groupItems);
    return cost;
}

export function groupMaxima(targets: Target[]): Record<string, number> {
    const found = idMap<number>();
    targets.forEach(({ field }) => {
        if (isRepeatingGroup(field)) found[field.id] = getRepeatSettings(field).maxItems;
    });
    return found;
}

// ---------------------------------------------------------------------------
// Evaluation
// ---------------------------------------------------------------------------

function truthy(value: unknown): boolean {
    if (value === null || value === undefined || value === false || value === '') return false;
    if (typeof value === 'number') return value !== 0;
    if (Array.isArray(value)) return value.length > 0;
    return true;
}

interface Scope {
    answers: Answers;
    variables: Record<string, unknown>;
    known: Set<string>;
    sources: LogicSources;
    today?: string;
    budget: Budget;
    costs: Map<FieldRule, number>;
}

/** Does the rule read something the form does not have, or its own question? Such a rule is never active. */
function dangling(rule: FieldRule, owner: string, scope: Scope): boolean {
    const when = rule.when;
    if (present(when?.expression)) {
        if (expressionVariables(when.expression).some((key) => !scope.known.has(key) || key === owner)) return true;
    } else {
        for (const condition of when?.conditions ?? []) {
            const source = String(condition?.fieldId ?? '');
            if (!source || source === owner || !(source in scope.sources)) return true;
            const child = condition?.childFieldId;
            if ((condition?.groupMode === 'ANY' || condition?.groupMode === 'ALL') && (!child || !(String(child) in scope.sources))) return true;
        }
    }
    return valueReads(rule).some((key) => !scope.known.has(key) || key === owner);
}

function evaluate(ast: unknown, scope: Scope): ExprValue {
    try {
        return evaluateExpression(ast as ExprNode, scope.variables, { today: scope.today ?? null });
    } catch {
        return null;
    }
}

function isActive(rule: FieldRule, owner: string, scope: Scope): boolean {
    if (dangling(rule, owner, scope)) return false;
    scope.budget.charge(scope.costs.get(rule) ?? 1);
    const when = rule.when;
    if (present(when?.expression)) return truthy(evaluate(when.expression, scope));
    try {
        return evaluateConditions((when?.operator || 'AND') as any, when?.conditions as any, scope.answers, scope.sources, MAX_INPUT_STRING_LENGTH);
    } catch {
        return false;
    }
}

/** The rules the evaluator reads: at most FIELD_RULES_MAX on a question, FORM_FIELD_RULES_MAX in the form (`allowance` counts down). */
function readRules(field: StandardFormFieldDto, allowance: { left: number }): FieldRule[] {
    const rules = rulesOf(field).slice(0, FIELD_RULES_MAX);
    const allowed = Math.max(0, Math.min(rules.length, allowance.left));
    allowance.left -= allowed;
    return rules.slice(0, allowed);
}

const CALENDAR_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Is `value` a real calendar date written exactly as YYYY-MM-DD (years 0001 to 9999)? */
export function isCalendarDate(value: unknown): value is string {
    if (typeof value !== 'string') return false;
    const match = CALENDAR_DATE.exec(value);
    if (!match) return false;
    const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
    if (year < 1) return false;
    // setUTCFullYear: Date.UTC treats the years 0 to 99 as 19xx.
    const date = new Date(0);
    date.setUTCFullYear(year, month - 1, day);
    return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

const choiceIds = (field: StandardFormFieldDto): Set<string> => new Set((field.properties?.choices ?? []).map((choice) => choice?.id).filter((id): id is string => !!id));

/**
 * The stored answer of a value a rule set for `field` (undefined when it is
 * empty or does not fit the field's type). `fromConst`: the value is a
 * rule's fixed `const`, which must itself be a number formulas can hold.
 */
export function valueAnswer(field: StandardFormFieldDto, value: unknown, fromConst = false): Answers | undefined {
    const type = field.type as string;
    if (TEXT_TYPES.has(type)) {
        const text = typeof value === 'string' ? value : formatExpressionValue(value as ExprValue);
        return text !== '' ? { type: 'text', text } : undefined;
    }
    if (type === FieldTypes.NUMBER) {
        if (typeof value !== 'number' || !Number.isFinite(value)) return undefined;
        // the numbers formulas can hold (15 significant digits, finite)
        if (fromConst && Dec.fromNumber(value) === null) return undefined;
        return { type: 'number', number: value };
    }
    if (type === FieldTypes.DATE) return isCalendarDate(value) ? { type: 'date', date: value } : undefined;
    if (type === FieldTypes.YES_NO) {
        if (typeof value === 'boolean') return { type: 'boolean', boolean: value };
        if (value === 'Yes' || value === 'true') return { type: 'boolean', boolean: true };
        if (value === 'No' || value === 'false') return { type: 'boolean', boolean: false };
        return undefined;
    }
    if (CHOICE_TYPES.has(type)) return typeof value === 'string' && choiceIds(field).has(value) ? { type: 'choice', choice: { value } } : undefined;
    return undefined;
}

function setValueOf(field: StandardFormFieldDto, rule: FieldRule, scope: Scope): Answers | undefined {
    const setValue = effect(rule, 'setValue') as FieldRuleEffect['setValue'];
    if (present(setValue?.const)) return valueAnswer(field, setValue!.const, true);
    if (CHOICE_TYPES.has(field.type)) return undefined; // a choice is set by a fixed option only
    return valueAnswer(field, evaluate(setValue?.expression, scope));
}

const KEY_SEPARATOR = '\u001f';
const stateKey = (fieldId: string, groupId?: string | null, item?: number | null): string => (groupId == null ? fieldId : [groupId, fieldId, item].join(KEY_SEPARATOR));

/** What the rules decided for one set of answers: which questions are locked, effective `required`, and the texts. */
export class FieldRuleStates {
    /** page questions whose value the form owns (never required) */
    readonly locked = new Set<string>();
    /** locked questions a rule gave a value (the form filled them in; the server has no twin, this is for what respondents are told) */
    readonly valued = new Set<string>();
    /** effective `required` where an active rule set it */
    readonly required = new Map<string, boolean>();
    /** `title` / `description` of the last active rules */
    readonly texts = new Map<string, { title?: string; description?: string }>();

    /** Effective required flag of a question (`staticRequired`: its own `validations.required`). */
    isRequired(fieldId: string, staticRequired: boolean, groupId?: string | null, item?: number | null): boolean {
        if (groupId == null && this.locked.has(fieldId)) return false;
        return this.required.get(stateKey(fieldId, groupId, item)) ?? staticRequired;
    }

    isLocked(fieldId: string): boolean {
        return this.locked.has(fieldId);
    }

    /** Title and description a rule gave the question, if any. */
    text(fieldId: string, groupId?: string | null, item?: number | null): { title?: string; description?: string } | undefined {
        return this.texts.get(stateKey(fieldId, groupId, item));
    }

    get isEmpty(): boolean {
        return !this.locked.size && !this.required.size && !this.texts.size;
    }
}

/** No rule decided anything. */
export const NO_RULES = new FieldRuleStates();

type ValueItem = { calc: StandardFormFieldDto } | { node: Target };
const idOf = (item: ValueItem): string => ('calc' in item ? item.calc.id : item.node.field.id);

/**
 * Calculated fields and set-value questions, each after the value nodes it
 * reads; those in a circle (only in data no save would accept) come last, in
 * form order, with no value.
 */
function valueOrder(nodes: Target[], calcs: StandardFormFieldDto[]): { ordered: ValueItem[]; cyclic: Set<string> } {
    const byId = new Map<string, ValueItem>();
    const deps = new Map<string, Set<string>>();
    calcs.forEach((calc) => {
        byId.set(calc.id, { calc });
        deps.set(calc.id, new Set(expressionVariables(calc.properties?.expression)));
    });
    nodes.forEach((node) => {
        byId.set(node.field.id, { node });
        const reads = new Set<string>();
        rulesOf(node.field)
            .filter(hasValueEffect)
            .forEach((rule) => ruleReads(rule).forEach((key) => reads.add(key)));
        deps.set(node.field.id, reads);
    });
    const calcIds = new Set(calcs.map((calc) => calc.id));
    deps.forEach((refs, key) => {
        // a calculation that reads itself stays in a circle (no value); a rule reading its own question is inactive anyway
        deps.set(key, new Set([...refs].filter((ref) => byId.has(ref) && (ref !== key || calcIds.has(key)))));
    });
    const ordered: ValueItem[] = [];
    const done = new Set<string>();
    let progress = true;
    while (progress) {
        progress = false;
        byId.forEach((item, key) => {
            if (done.has(key) || [...deps.get(key)!].some((ref) => !done.has(ref))) return;
            done.add(key);
            ordered.push(item);
            progress = true;
        });
    }
    const cyclic = new Set([...byId.keys()].filter((key) => !done.has(key)));
    byId.forEach((item, key) => cyclic.has(key) && ordered.push(item));
    return { ordered, cyclic };
}

/** How many items a repeating group shows (at least the minimum, at most the maximum). */
const itemCount = (group: StandardFormFieldDto, items: unknown[]): number => {
    const { minItems, maxItems } = getRepeatSettings(group);
    return Math.min(maxItems, Math.max(minItems, items.length));
};

function applyStates(rules: FieldRule[], owner: string, scope: Scope, key: string, states: FieldRuleStates): void {
    let required: boolean | undefined;
    const texts: { title?: string; description?: string } = {};
    rules.forEach((rule) => {
        if (!hasStateEffect(rule) || !isActive(rule, owner, scope)) return;
        if (present(effect(rule, 'required'))) required = !!effect(rule, 'required');
        (['title', 'description'] as const).forEach((name) => {
            const text = effect(rule, name);
            if (present(text)) texts[name] = text as string;
        });
    });
    if (required !== undefined) states.required.set(key, required);
    if (Object.keys(texts).length) states.texts.set(key, texts);
}

export interface ResolvedFieldRules {
    /** The answers with the form's values (calculated fields and what rules set or lock). The same object when nothing was derived. */
    answers: Answers;
    states: FieldRuleStates;
    /** Question ids whose answer the form owns here: every calculated field and each set-value or lockable question. */
    derivedIds: Set<string>;
    /** The rules were over their evaluation budget: no rule was applied (the server would refuse such a response). */
    tooCostly?: boolean;
}

/**
 * The answers with the form's values and the states the rules give the
 * questions, from the answers as they are now. What was given for a
 * calculated field, or for a question while a rule sets or locks it, is
 * dropped. Twin of the server's `resolve_field_rules`.
 *
 * `hiddenNames`: the form's declared hidden fields (a rule may read one that
 * the link did not fill); without it, the names that have a value.
 */
export function resolveFieldRules(slides: StandardFormFieldDto[] | undefined | null, answers: Answers | undefined | null, hiddenValues: Record<string, string> = {}, today?: string, hiddenNames?: string[]): ResolvedFieldRules {
    const input = answers ?? {};
    const calculated = getCalculatedFields(slides);
    const calcs = calculated.filter((field) => field.id && !field.internal);
    const targets = targetsOf(slides).filter((target) => rulesOf(target.field).length > 0);
    const derivedIds = new Set<string>();
    if (!calculated.length && !targets.length) return { answers: input, states: NO_RULES, derivedIds };

    // No prototype: a question id is creator content, `__proto__` included.
    const out: Answers = idMap(input);
    calculated.forEach((calc) => delete out[calc.id]);
    const plain: Answers = idMap(out);
    const names = hiddenNames ?? Object.keys(hiddenValues ?? {});
    const variables = buildVariables(slides, plain, hiddenValues, hiddenNames);
    const known = new Set(calculationVariables(slides, names).map((variable) => variable.key));
    // What respondents are served: no internal question (a condition that reads
    // one is not active, as on the server, which drops their answers).
    const sources = idMap<StandardFormFieldDto>();
    Object.entries(logicSourcesById(slides)).forEach(([id, field]) => !field.internal && (sources[id] = field));
    const questions = questionKeys(slides);
    const states = new FieldRuleStates();
    const allowance = { left: FORM_FIELD_RULES_MAX };
    const read = new Map<StandardFormFieldDto, FieldRule[]>();
    targets.forEach((target) => read.set(target.field, readRules(target.field, allowance)));
    const nodes = targets.filter(isValueNode);
    const maxima = groupMaxima(targetsOf(slides));
    const costs = new Map<FieldRule, number>();
    read.forEach((rules) => rules.forEach((rule) => costs.set(rule, ruleCost(rule, maxima))));
    const scope: Scope = { answers: plain, variables, known, sources, today, budget: new Budget(), costs };

    try {
        const { ordered, cyclic } = valueOrder(nodes, calcs);
        ordered.forEach((item) => {
            const id = idOf(item);
            if ('calc' in item) {
                let value: ExprValue = null;
                if (!cyclic.has(id)) {
                    const expression = item.calc.properties?.expression;
                    if (expression !== undefined && expression !== null) value = evaluate(expression, { ...scope, variables: readingFor(item.calc, variables, questions) });
                }
                variables[id] = value;
                const answer = calculatedAnswer(value);
                plain[id] = answer ?? { type: 'text' };
                if (answer) out[id] = answer;
                derivedIds.add(id);
                return;
            }
            const field = item.node.field;
            const active = (read.get(field) ?? []).filter((rule) => hasValueEffect(rule) && isActive(rule, id, scope));
            if (!active.length) return;
            const setter = [...active].reverse().find((rule) => present(effect(rule, 'setValue')));
            // a value in a circle has no value (as a calculation in one has not), so the answers settle
            const answer = setter && !cyclic.has(id) ? setValueOf(field, setter, scope) : undefined;
            states.locked.add(id);
            derivedIds.add(id);
            if (answer) {
                states.valued.add(id);
                out[id] = answer;
                plain[id] = answer;
            } else {
                delete out[id];
                delete plain[id];
            }
            variables[id] = getComparableAnswerValue(plain[id], field.type) ?? null;
        });

        const groups = new Map<string, StandardFormFieldDto>();
        targets.forEach((target) => {
            const rules = read.get(target.field) ?? [];
            if (!rules.length) return;
            if (!target.group) applyStates(rules, target.field.id, scope, stateKey(target.field.id), states);
            else groups.set(target.group.id, target.group);
        });
        groups.forEach((group, groupId) => {
            const items = getGroupAnswerItems(plain[groupId]);
            const children = group.properties?.fields ?? [];
            const siblings = new Set(children.map((child) => child.id).filter(Boolean));
            for (let index = 0; index < itemCount(group, items); index++) {
                const item = items[index] ?? {};
                const siblingVariables = idMap<unknown>();
                children.forEach((child) => child.id && (siblingVariables[child.id] = getComparableAnswerValue(item[child.id], child.type) ?? null));
                const itemScope: Scope = { ...scope, answers: idMap({ ...plain, ...item }), variables: idMap({ ...variables, ...siblingVariables }), known: new Set([...known, ...siblings]) };
                children.forEach((child) => {
                    const rules = read.get(child) ?? [];
                    if (rules.length) applyStates(rules, child.id, itemScope, stateKey(child.id, groupId, index), states);
                });
            }
        });
    } catch (error) {
        if (error instanceof TooCostly) return { answers: input, states: NO_RULES, derivedIds: new Set(), tooCostly: true };
        throw error;
    }
    return { answers: out, states, derivedIds };
}

/** Only the states (the answers are left as they are). */
export function fieldRuleStates(slides: StandardFormFieldDto[] | undefined | null, answers: Answers | undefined | null, hiddenValues: Record<string, string> = {}, today?: string, hiddenNames?: string[]): FieldRuleStates {
    return resolveFieldRules(slides, answers, hiddenValues, today, hiddenNames).states;
}

const same = (a: unknown, b: unknown): boolean => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/**
 * `answers` with the form's values written in (calculated fields and the
 * values rules set or lock), and the states. The same `answers` object when
 * nothing differs, so an effect that writes them settles. `basis`: the answers
 * the values are worked out from (what a submission would carry); only the
 * derived answers are written into `answers`, the rest is left as it is.
 */
export function withDerivedAnswers(
    slides: StandardFormFieldDto[] | undefined | null,
    answers: Answers | undefined | null,
    hiddenValues: Record<string, string> = {},
    today?: string,
    hiddenNames?: string[],
    basis?: (answers: Answers) => Answers
): { answers: Answers; states: FieldRuleStates } {
    const current = answers ?? {};
    const resolved = resolveFieldRules(slides, basis ? basis(current) : current, hiddenValues, today, hiddenNames);
    let next: Answers | null = null;
    resolved.derivedIds.forEach((id) => {
        if (same(current[id], resolved.answers[id])) return;
        next = next ?? idMap(current);
        if (resolved.answers[id] === undefined) delete next[id];
        else next[id] = resolved.answers[id];
    });
    return { answers: next ?? (answers as Answers), states: resolved.states };
}
