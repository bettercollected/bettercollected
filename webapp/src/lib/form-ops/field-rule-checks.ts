/**
 * Save-time checks of field rules (`properties.rules`): the twin of the
 * backend's `field_rule_problems` and `prune_field_rules`
 * (services/field_rules.py), with the same messages, caps and order.
 *
 * The ops engine uses it to refuse a `set_field_rules` that would not save
 * and to drop the rules a structural edit left dangling; the rules editor
 * shows the same problems inline, so the builder and the server never
 * disagree about what a valid rule is. Pure: reads a document, changes
 * nothing.
 */
import { validateExpression } from '@app/lib/expressions/validator';
import {
    FIELD_RULES_MAX,
    FORM_FIELD_RULES_MAX,
    type FieldRule,
    RULE_COST_PER_RESPONSE,
    type Target,
    groupMaxima,
    hasStateEffect,
    hasValueEffect,
    isMultiple,
    isValueNode,
    present,
    ruleCost,
    ruleReads,
    rulesOf,
    targetsOf,
    valueAnswer
} from '@app/lib/field-rules';
import { FieldTypes, type StandardFormFieldDto } from '@app/models/dtos/form';
import { expressionVariables } from '@app/utils/calculated-fields';

import { calcTitle, pageFields, variableKeys } from './calculations';
import { childrenOf, isRepeatingGroup, isSlide } from './model';
import type { FormDoc, FormField } from './types';

/** Problems one check reports at most (the backend's PROBLEMS_MAX). */
export const PROBLEMS_MAX = 50;
/** Distinct variables one rule expression may read. */
export const RULE_VARIABLES_MAX = 50;

const COMPARISONS = new Set(['IS_EMPTY', 'IS_NOT_EMPTY', 'IS_EQUAL', 'IS_NOT_EQUAL', 'CONTAINS', 'DOES_NOT_CONTAIN', 'LESS_THAN', 'LESS_THAN_EQUAL', 'GREATER_THAN', 'GREATER_THAN_EQUAL', 'STARTS_WITH', 'ENDS_WITH']);
const GROUP_MODES = new Set(['COUNT', 'ANY', 'ALL']);
const TEXT_TYPES = new Set<string>([FieldTypes.SHORT_TEXT, FieldTypes.LONG_TEXT]);
const CHOICE_TYPES = new Set<string>([FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN]);
const VALUE_TYPES = new Set<string>([...TEXT_TYPES, ...CHOICE_TYPES, FieldTypes.NUMBER, FieldTypes.DATE, FieldTypes.YES_NO]);
/** Types that hold no answer a rule could apply to (content, pages, hidden and calculated fields, groups). */
const NOT_RULE_TARGETS = new Set<string>([
    'slide',
    'matrix',
    'text',
    'statement',
    'page_break',
    'hidden',
    'conditional',
    'payment',
    'tabular_input',
    'file_upload',
    'VIDEO_CONTENT',
    'IMAGE_CONTENT',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'p',
    'strong',
    'divider',
    'markdown',
    FieldTypes.CALCULATED,
    FieldTypes.GROUP
]);
const PIPE = /\{\{\s*(field|hidden|group)\s*:\s*([^|}]*?)\s*(?:\|[^}]*)?\}\}/g;

/** What a form is for these checks: its pages and hidden-field names. */
export interface RuleForm {
    fields?: FormField[] | StandardFormFieldDto[] | null;
    hiddenFields?: string[] | null;
}

export interface FieldRuleProblem {
    fieldId: string;
    /** JSON pointer into the question's `rules` ("" = all of them). */
    path: string;
    message: string;
    /** Position of the rule the problem is about. */
    rule?: number;
    /** The question itself cannot carry rules: none of them can stand. */
    wholeField?: boolean;
}

const pointer = (...parts: Array<string | number>): string => parts.map((part) => '/' + String(part).replace(/~/g, '~0').replace(/\//g, '~1')).join('');

const asDto = (fields: RuleForm['fields']) => fields as StandardFormFieldDto[] | undefined | null;
const titleOf = (field: StandardFormFieldDto) => calcTitle(field as unknown as FormField);
const childList = (field: StandardFormFieldDto | undefined): StandardFormFieldDto[] => (field ? (childrenOf(field as unknown as FormField) as unknown as StandardFormFieldDto[]) : []);
const rulesOnField = (field: unknown): FieldRule[] => rulesOf(field as StandardFormFieldDto);

/** Every field of the form, anywhere (a misplaced one too), with the path from `form.fields`. */
export function walkFields(form: RuleForm): Array<{ field: FormField; path: number[] }> {
    const found: Array<{ field: FormField; path: number[] }> = [];
    const pending: Array<{ field: FormField; path: number[] }> = ((form.fields ?? []) as FormField[]).map((field, i) => ({ field, path: [i] })).reverse();
    while (pending.length) {
        const item = pending.pop()!;
        if (!item.field || typeof item.field !== 'object') continue;
        found.push(item);
        const children = childrenOf(item.field);
        for (let i = children.length - 1; i >= 0; i--) pending.push({ field: children[i], path: [...item.path, i] });
    }
    return found;
}

export function totalRules(form: RuleForm): number {
    let total = 0;
    for (const { field } of walkFields(form)) total += rulesOnField(field).length;
    return total;
}

/** Does any question carry rules? (cheap: stops at the first) */
export function hasFieldRules(form: RuleForm): boolean {
    const pending: unknown[] = [...((form.fields ?? []) as unknown[])];
    while (pending.length) {
        const field = pending.pop() as FormField | undefined;
        if (!field || typeof field !== 'object') continue;
        if (Array.isArray((field.properties as any)?.rules) && (field.properties as any).rules.length) return true;
        pending.push(...childrenOf(field));
    }
    return false;
}

const siblingIds = (target: Target): Set<string> =>
    new Set(
        childList(target.group)
            .map((child) => String(child.id ?? ''))
            .filter(Boolean)
    );

function questionCost(target: Target, maxima: Record<string, number>): number {
    const times = target.group ? (maxima[target.group.id] ?? 1) : 1;
    let total = 0;
    for (const rule of rulesOnField(target.field).slice(0, FIELD_RULES_MAX)) total += ruleCost(rule, maxima) * times * (Number(hasValueEffect(rule)) + Number(hasStateEffect(rule)));
    return total;
}

/** The first path from `start` back to itself, or null (iterative DFS). */
function cycleThrough(start: string, edges: Map<string, Set<string>>): string[] | null {
    const stack: Array<[string, string[]]> = [[start, [start]]];
    const seen = new Set<string>();
    while (stack.length) {
        const [node, path] = stack.pop()!;
        for (const ref of [...(edges.get(node) ?? [])].sort()) {
            if (ref === start) return path;
            if (!seen.has(ref)) {
                seen.add(ref);
                stack.push([ref, [...path, ref]]);
            }
        }
    }
    return null;
}

/** The JSON pointer of the first `{"var": key}` of an AST, breadth first. */
function varPointer(ast: unknown, key: string): string {
    const pending: Array<[unknown, string]> = [[ast, '']];
    let head = 0;
    while (head < pending.length) {
        const [node, path] = pending[head++];
        if (!node || typeof node !== 'object' || Array.isArray(node)) continue;
        const entries = Object.entries(node as Record<string, unknown>);
        if (entries.length !== 1) continue;
        const [op, value] = entries[0];
        const here = path + pointer(op);
        if (op === 'var' && value === key) return here;
        if (Array.isArray(value)) value.forEach((child, i) => pending.push([child, `${here}/${i}`]));
    }
    return '';
}

class Enough extends Error {}

export interface CheckOptions {
    /** Report at most this many problems (default PROBLEMS_MAX; null: all). */
    limit?: number | null;
    /** Check the rules of these questions alone (plus what spans the form: ids, circles, cost). */
    only?: Iterable<string>;
}

class Checker {
    problems: FieldRuleProblem[] = [];
    readonly targets: Target[];
    readonly byId = new Map<string, Target>();
    readonly pages = new Set<string>();
    readonly known: Set<string>;
    readonly hiddenNames: Set<string>;
    readonly internal = new Set<string>();
    readonly maxima: Record<string, number>;
    readonly limit: number | null;
    readonly only: Set<string> | null;
    private readonly siblingCache = new Map<StandardFormFieldDto | undefined, Set<string>>();

    constructor(
        readonly form: RuleForm,
        options: CheckOptions = {}
    ) {
        this.limit = options.limit === undefined ? PROBLEMS_MAX : options.limit;
        this.only = options.only ? new Set(options.only) : null;
        const slides = asDto(form.fields);
        this.targets = targetsOf(slides);
        for (const target of this.targets) {
            if (target.field.id) this.byId.set(target.field.id, target);
            if (target.field.internal && target.field.id) this.internal.add(target.field.id);
        }
        for (const page of (form.fields ?? []) as FormField[]) if (isSlide(page)) this.pages.add(String(page.id));
        this.known = variableKeys(form as FormDoc);
        this.hiddenNames = new Set((form.hiddenFields ?? []).map(String));
        this.maxima = groupMaxima(this.targets);
    }

    run(): FieldRuleProblem[] {
        this.problems = [];
        const total = totalRules(this.form);
        if (!total) return this.problems;
        if (total > FORM_FIELD_RULES_MAX) {
            // Nothing else is looked at: the per-rule checks would be paid for every rule of an oversized form.
            return [{ fieldId: '', path: '', message: `A form can have at most ${FORM_FIELD_RULES_MAX} rules; this one has ${total}.` }];
        }
        try {
            this.check();
        } catch (error) {
            if (!(error instanceof Enough)) throw error;
        }
        return this.problems;
    }

    private siblings(target: Target): Set<string> {
        let found = this.siblingCache.get(target.group);
        if (!found) {
            found = siblingIds(target);
            this.siblingCache.set(target.group, found);
        }
        return found;
    }

    private add(fieldId: string, path: string, message: string, rule?: number, wholeField = false) {
        this.problems.push({ fieldId, path, message, ...(rule !== undefined ? { rule } : {}), ...(wholeField ? { wholeField } : {}) });
        if (this.limit !== null && this.problems.length >= this.limit) throw new Enough();
    }

    private misplaced() {
        // the server's walk: a stack, the last field first, its children after it
        const onQuestions = new Set(this.targets.map((target) => target.field as unknown));
        const pending: FormField[] = [...((this.form.fields ?? []) as FormField[])];
        while (pending.length) {
            const field = pending.pop()!;
            if (!field || typeof field !== 'object') continue;
            pending.push(...childrenOf(field));
            if (rulesOnField(field).length && !onQuestions.has(field)) {
                this.add(String(field.id ?? ''), '', `'${titleOf(field as unknown as StandardFormFieldDto)}' cannot have rules: only questions on the pages of a form (or in a repeating group) can.`, undefined, true);
            }
        }
    }

    private check() {
        this.misplaced();
        const seen = new Map<string, string>();
        for (const target of this.targets) {
            const rules = rulesOnField(target.field);
            if (!rules.length) continue;
            const checked = this.only === null || this.only.has(target.field.id);
            if (checked) this.target(target);
            rules.forEach((rule, index) => {
                const ruleId = String(rule?.id ?? '');
                if (seen.has(ruleId)) this.add(target.field.id, pointer(index, 'id'), `The rule id '${ruleId}' is used more than once in this form.`, index);
                if (!seen.has(ruleId)) seen.set(ruleId, target.field.id);
                if (checked) this.rule(target, index, rule);
            });
        }
        this.cycles();
        let cost = 0;
        for (const target of this.targets) if (rulesOnField(target.field).length) cost += questionCost(target, this.maxima);
        if (cost > RULE_COST_PER_RESPONSE) {
            this.add('', '', `These rules would take too long to check for each response (cost ${cost}, at most ${RULE_COST_PER_RESPONSE}): use fewer or shorter rules, or fewer items in the repeating groups they are in.`);
        }
    }

    private target(target: Target) {
        const { field } = target;
        const name = titleOf(field);
        if (field.internal) {
            this.add(field.id, '', `'${name}' is an internal field: rules apply to what respondents answer.`, undefined, true);
        } else if (NOT_RULE_TARGETS.has(field.type)) {
            this.add(field.id, '', `'${name}' cannot have rules: rules apply to questions with one answer (not content, calculations, groups, matrices, uploads, tables or payments).`, undefined, true);
        }
    }

    private rule(target: Target, index: number, rule: FieldRule) {
        const { field } = target;
        const name = titleOf(field);
        const when = rule.when;
        if (present(when?.expression)) this.expression(target, index, when.expression, ['when', 'expression']);
        else (when?.conditions ?? []).forEach((condition, c) => this.condition(target, index, c, condition));
        const then = rule.then;
        if (hasValueEffect(rule)) {
            let problem: string | null = null;
            if (target.group) problem = `'${name}' is in a repeating group: rules cannot lock or set the value of a group's questions.`;
            else if (!VALUE_TYPES.has(field.type)) problem = `Rules can lock or set the value of short and long text, number, date, yes/no and single-choice questions, not '${name}'.`;
            else if (isMultiple(field)) problem = `'${name}' allows several choices: rules can only set the value of a single-choice question.`;
            if (problem) this.add(field.id, pointer(index, 'then', present(then?.setValue) ? 'setValue' : 'readOnly'), problem, index);
            else this.setValue(target, index, then?.setValue);
        }
        for (const key of ['title', 'description'] as const) {
            const text = then?.[key];
            if (typeof text === 'string') this.pipes(target, index, text, ['then', key]);
        }
    }

    private condition(target: Target, index: number, c: number, condition: NonNullable<FieldRule['when']['conditions']>[number]) {
        const here: Array<string | number> = [index, 'when', 'conditions', c];
        const name = titleOf(target.field);
        const sourceId = String(condition?.fieldId ?? '');
        if (!COMPARISONS.has(String(condition?.comparison))) this.add(target.field.id, pointer(...here, 'comparison'), `A rule of '${name}' has a condition without a known comparison.`, index);
        if (!sourceId) {
            this.add(target.field.id, pointer(...here, 'fieldId'), `A condition of a rule of '${name}' needs a question.`, index);
            return;
        }
        if (sourceId === target.field.id) {
            this.add(target.field.id, pointer(...here, 'fieldId'), `A rule of '${name}' cannot depend on the question's own answer.`, index);
            return;
        }
        const source = this.byId.get(sourceId);
        if (!source) {
            const what = this.pages.has(sourceId) ? 'a page' : 'no question';
            this.add(target.field.id, pointer(...here, 'fieldId'), `A rule of '${name}' uses '${sourceId}', which is ${what} of this form.`, index);
            return;
        }
        const sourceName = titleOf(source.field);
        if (source.field.internal) {
            this.add(target.field.id, pointer(...here, 'fieldId'), `A rule of '${name}' uses the internal field '${sourceName}': respondents never answer internal fields.`, index);
            return;
        }
        const targetGroup = target.group?.id ?? null;
        if (source.group && (source.group.id ?? null) !== targetGroup) {
            this.add(target.field.id, pointer(...here, 'fieldId'), `A rule of '${name}' uses '${sourceName}', which is asked once per item of a repeating group: outside the group, use the group itself with groupMode COUNT, ANY or ALL.`, index);
            return;
        }
        const groupMode = condition.groupMode;
        const isGroup = isRepeatingGroup(source.field as unknown as FormField);
        if (isGroup && !GROUP_MODES.has(String(groupMode))) {
            this.add(target.field.id, pointer(...here, 'groupMode'), `'${sourceName}' is a repeating group: a condition on it needs groupMode COUNT, ANY or ALL.`, index);
        } else if (!isGroup && groupMode) {
            this.add(target.field.id, pointer(...here, 'groupMode'), `groupMode only applies to repeating groups, not '${sourceName}'.`, index);
        } else if (isGroup && (groupMode === 'ANY' || groupMode === 'ALL')) {
            const child = String(condition.childFieldId ?? '');
            if (!childList(source.field).some((c) => String(c.id) === child)) {
                this.add(target.field.id, pointer(...here, 'childFieldId'), `An ANY/ALL condition on '${sourceName}' needs childFieldId: one of the group's questions.`, index);
            }
            if (targetGroup === source.field.id) this.add(target.field.id, pointer(...here, 'fieldId'), `A rule of '${name}' cannot use its own repeating group.`, index);
        } else if (isGroup && targetGroup === source.field.id) {
            this.add(target.field.id, pointer(...here, 'fieldId'), `A rule of '${name}' cannot use its own repeating group.`, index);
        }
    }

    private expression(target: Target, index: number, ast: unknown, where: string[]) {
        const name = titleOf(target.field);
        const structural = validateExpression(ast);
        if (structural.length) {
            for (const problem of structural) this.add(target.field.id, pointer(index, ...where) + problem.path, `A rule of '${name}': ${problem.message}`, index);
            return;
        }
        // inside an item, a sibling's id reads that item's answer
        const siblings = target.group ? this.siblings(target) : new Set<string>();
        const reads = (key: string) => this.known.has(key) || siblings.has(key);
        const keys = expressionVariables(ast);
        if (keys.length > RULE_VARIABLES_MAX) {
            this.add(target.field.id, pointer(index, ...where), `A rule of '${name}' reads ${keys.length} variables; an expression can read at most ${RULE_VARIABLES_MAX}.`, index);
            return;
        }
        for (const key of keys) {
            if (reads(key) && key !== target.field.id && !this.internal.has(key)) continue;
            const path = pointer(index, ...where) + varPointer(ast, key);
            if (key === target.field.id) this.add(target.field.id, path, `A rule of '${name}' cannot read the question's own value.`, index);
            else if (this.internal.has(key)) this.add(target.field.id, path, `A rule of '${name}' uses an internal field: respondents never answer internal fields.`, index);
            else if (!reads(key)) this.add(target.field.id, path, `A rule of '${name}' uses '${key}', which is not a question, calculation or hidden field it can read.`, index);
        }
    }

    private setValue(target: Target, index: number, setValue: FieldRule['then']['setValue']) {
        if (!present(setValue)) return;
        const { field } = target;
        const name = titleOf(field);
        const here: Array<string | number> = [index, 'then', 'setValue'];
        const expression = setValue!.expression;
        if (present(expression)) {
            if (CHOICE_TYPES.has(field.type)) {
                this.add(target.field.id, pointer(...here, 'expression'), `'${name}' is a choice question: a rule sets it to one of its options with 'const' (the option's id), not an expression.`, index);
                return;
            }
            this.expression(target, index, expression, ['then', 'setValue', 'expression']);
            return;
        }
        if (valueAnswer(field, setValue!.const, true) === undefined) {
            const what =
                (
                    {
                        [FieldTypes.NUMBER]: 'a number',
                        [FieldTypes.DATE]: 'a date written as YYYY-MM-DD',
                        [FieldTypes.YES_NO]: 'true or false',
                        [FieldTypes.MULTIPLE_CHOICE]: 'the id of one of its options',
                        [FieldTypes.DROP_DOWN]: 'the id of one of its options'
                    } as Record<string, string>
                )[field.type] ?? 'a text';
            this.add(target.field.id, pointer(...here, 'const'), `A rule of '${name}' sets a value that does not fit it: use ${what}.`, index);
        }
    }

    private pipes(target: Target, index: number, text: string, where: string[]) {
        const name = titleOf(target.field);
        const siblings = target.group ? this.siblings(target) : new Set<string>();
        for (const match of text.matchAll(PIPE)) {
            const [, kind, key] = match;
            let ok: boolean;
            if (kind === 'hidden') ok = this.hiddenNames.has(key);
            else if (kind === 'group') {
                const group = this.byId.get(key.split(':', 1)[0]);
                ok = !!group && isRepeatingGroup(group.field as unknown as FormField);
            } else {
                const source = this.byId.get(key);
                ok = !!source && !source.field.internal && (!source.group || siblings.has(key));
            }
            if (!ok) this.add(target.field.id, pointer(index, ...where), `A rule of '${name}' pipes '${key}', which this form does not have (or the text cannot show).`, index);
        }
    }

    /** Set values and calculations must not depend on each other in a circle (circles of calculations alone are the calculations' to report). */
    private cycles() {
        const nodes = this.targets.filter(isValueNode);
        if (!nodes.length) return;
        const edges = new Map<string, Set<string>>();
        for (const calc of pageFields(this.form as FormDoc).filter((field) => field.type === FieldTypes.CALCULATED)) edges.set(String(calc.id), new Set(expressionVariables(calc.properties?.expression)));
        for (const node of nodes) {
            const reads = new Set<string>();
            for (const rule of rulesOnField(node.field)) if (hasValueEffect(rule)) for (const key of ruleReads(rule)) reads.add(key);
            edges.set(node.field.id, reads);
        }
        const cleaned = new Map<string, Set<string>>();
        edges.forEach((refs, key) => cleaned.set(key, new Set([...refs].filter((ref) => edges.has(ref) && ref !== key))));
        const reported = new Set<string>();
        for (const node of nodes) {
            const cycle = cycleThrough(node.field.id, cleaned);
            if (!cycle) continue;
            const signature = [...new Set(cycle)].sort().join('\u0000');
            if (reported.has(signature)) continue;
            reported.add(signature);
            const names = cycle.map((key) => (this.byId.has(key) ? titleOf(this.byId.get(key)!.field) : key));
            this.add(node.field.id, '', `Set values and calculations cannot depend on each other in a circle (${[...names, ...names.slice(0, 1)].map((n) => `'${n}'`).join(' → ')}).`);
        }
    }
}

/** A checker for `form` (`.run()` gives the problems): run it before and after replacing the rules of the questions in `only`. */
export function fieldRuleChecker(form: RuleForm, options: CheckOptions = {}): { run: () => FieldRuleProblem[] } {
    const checker = new Checker(form, options);
    return { run: () => checker.run() };
}

/** Problems with the rules of a form (see the backend's field_rules module doc). */
export function fieldRuleProblems(form: RuleForm, options: CheckOptions = {}): FieldRuleProblem[] {
    if (!hasFieldRules(form)) return [];
    return new Checker(form, options).run();
}

export interface FieldRuleFix {
    path: number[];
    /** The rules to keep; undefined clears them. */
    rules: FieldRule[] | undefined;
    dropped: number;
}

/**
 * The rules a structural edit left dangling, as fixes to make (backend
 * `prune_field_rules`): every rule with a problem of its own (references,
 * targets, values), and every rule of a question that cannot carry rules at
 * all (internal, misplaced, of a type without rules). Form-wide problems
 * (caps, circles, cost) are left to the check.
 */
export function fieldRuleFixes(form: RuleForm): FieldRuleFix[] {
    if (!hasFieldRules(form)) return [];
    const problems = new Checker(form, { limit: null }).run();
    const first = new Map<string, FieldRuleProblem>();
    const whole = new Map<string, FieldRuleProblem>();
    for (const problem of problems) {
        if (problem.wholeField && problem.fieldId) {
            if (!whole.has(problem.fieldId)) whole.set(problem.fieldId, problem);
        } else if (problem.rule !== undefined) {
            const key = `${problem.fieldId}\u0000${problem.rule}`;
            if (!first.has(key)) first.set(key, problem);
        }
    }
    if (!first.size && !whole.size) return [];
    const owners = new Set<string>([...whole.keys(), ...[...first.keys()].map((key) => key.split('\u0000')[0])]);
    const fixes: FieldRuleFix[] = [];
    for (const { field, path } of walkFields(form)) {
        const id = String(field.id ?? '');
        const rules = rulesOnField(field);
        if (!rules.length || !owners.has(id)) continue;
        const kept = rules.filter((_, index) => !whole.has(id) && !first.has(`${id}\u0000${index}`));
        if (kept.length !== rules.length) fixes.push({ path, rules: kept.length ? kept : undefined, dropped: rules.length - kept.length });
    }
    return fixes;
}

/** May this question carry rules at all (it is a question of one answer that respondents answer)? */
export function canCarryRules(field: { type?: string; internal?: boolean | null }): boolean {
    return !field.internal && !NOT_RULE_TARGETS.has(String(field.type));
}

/** May a rule lock or set the value of this question (`inGroup`: it is a repeating group's question)? */
export function canLockOrSet(field: { type?: string; internal?: boolean | null; properties?: { allowMultipleSelection?: boolean | null } | null }, inGroup: boolean): boolean {
    return canCarryRules(field) && !inGroup && VALUE_TYPES.has(String(field.type)) && !(field.type === FieldTypes.MULTIPLE_CHOICE && !!field.properties?.allowMultipleSelection);
}
