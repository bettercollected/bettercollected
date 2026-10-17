/**
 * Calculated fields in the ops engine: the twin of the backend's
 * `calculated_field_problems` (services/calculated_fields.py) and
 * `_set_calculation` / `_calculation_message` (services/ai/ops.py), with the
 * same messages. Every op that leaves a calculation broken (an unknown or
 * internal field, a circle, a malformed expression) is refused and undone.
 */
import { validateExpression } from '@app/lib/expressions/validator';
import { FieldTypes } from '@app/models/dtos/form';

import { findCycle } from './date-rules';
import { OpError, isRepeatingGroup, isSlide } from './model';
import type { FormDoc, FormField } from './types';

/** Field types whose answer a formula cannot read (backend NOT_VARIABLES). */
const NOT_VARIABLES = new Set<string>([
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
    'markdown'
]);

export interface CalculationProblem {
    fieldId: string;
    path: string;
    message: string;
}

function plainText(node: any): string {
    if (!node || typeof node !== 'object') return '';
    if (node.type === 'text' && typeof node.text === 'string') return node.text;
    return ((node.content as any[]) ?? []).map(plainText).join('');
}

/** A calculation's name in messages (backend calculated_fields `_title`). */
function calcTitle(field: FormField): string {
    const title = field.title as any;
    if (typeof title === 'string' && title.trim()) return title.trim();
    if (title && typeof title === 'object') {
        const text = plainText(title).trim();
        if (text) return text;
    }
    return String(field.id || 'a calculation');
}

function pageFields(doc: FormDoc): FormField[] {
    const fields = (doc.fields ?? []) as FormField[];
    if (!fields.length || fields.some((field) => !isSlide(field))) return [];
    return fields.flatMap((page) => ((page.properties?.fields as FormField[] | undefined) ?? []).filter(Boolean));
}

const isCalculated = (field: FormField | undefined | null) => field?.type === FieldTypes.CALCULATED;

// Per page object: documents are immutable and unchanged pages keep their
// reference, so a batch looks into each changed page once.
const pageHasCalculation = new WeakMap<object, boolean>();

const docHasCalculation = new WeakMap<object, boolean>();

export function hasCalculations(doc: FormDoc): boolean {
    const known = docHasCalculation.get(doc);
    if (known !== undefined) return known;
    const has = scanCalculations(doc);
    docHasCalculation.set(doc, has);
    return has;
}

function scanCalculations(doc: FormDoc): boolean {
    for (const page of (doc.fields ?? []) as FormField[]) {
        if (!page || typeof page !== 'object') continue;
        let has = pageHasCalculation.get(page);
        if (has === undefined) {
            // anywhere in the page, groups included (a misplaced one is a problem too)
            const pending = [page];
            has = false;
            while (pending.length && !has) {
                const field = pending.pop()!;
                if (isCalculated(field)) has = true;
                else pending.push(...(((field?.properties?.fields as FormField[] | undefined) ?? []) as FormField[]));
            }
            pageHasCalculation.set(page, has);
        }
        if (has) return true;
    }
    return false;
}

/** Does an op bring a calculated field or an expression? (backend `_carries_calculation`) */
export function carriesCalculation(op: unknown): boolean {
    const pending: unknown[] = [op];
    while (pending.length) {
        const value = pending.pop();
        if (Array.isArray(value)) pending.push(...value);
        else if (value && typeof value === 'object') {
            const item = value as Record<string, unknown>;
            if (item.type === FieldTypes.CALCULATED || 'expression' in item) return true;
            pending.push(...Object.values(item));
        }
    }
    return false;
}

/**
 * Could the op have broken a calculation? Only when the form had one, or
 * the op brings one (backend apply_form_ops: the same condition), so forms
 * without calculations pay one cached lookup per op.
 */
export const calculationsTouched = (before: FormDoc, after: FormDoc, op: unknown): boolean => before !== after && (hasCalculations(before) || carriesCalculation(op));

function variableKeys(doc: FormDoc): Set<string> {
    const keys = new Set<string>((doc.hiddenFields ?? []).map(String));
    for (const field of pageFields(doc)) {
        if (!field.id || field.internal) continue;
        if (isRepeatingGroup(field)) {
            for (const child of (field.properties?.fields as FormField[] | undefined) ?? []) if (child?.id && !child.internal) keys.add(`${field.id}.${child.id}`);
            continue;
        }
        if (NOT_VARIABLES.has(field.type) || field.type === FieldTypes.GROUP) continue;
        keys.add(String(field.id));
    }
    return keys;
}

function expressionVariables(ast: unknown): string[] {
    const found: string[] = [];
    const pending: unknown[] = [ast];
    while (pending.length) {
        const node = pending.pop();
        if (!node || typeof node !== 'object' || Array.isArray(node)) continue;
        const entries = Object.entries(node as Record<string, unknown>);
        if (entries.length !== 1) continue;
        const [op, value] = entries[0];
        if (op === 'var') {
            if (typeof value === 'string' && !found.includes(value)) found.push(value);
        } else if (Array.isArray(value)) pending.push(...[...value].reverse());
    }
    return found;
}

function varAt(ast: unknown, pointer: string): string | null {
    let node: any = ast;
    for (const part of pointer
        .split('/')
        .slice(1)
        .map((p) => p.replace(/~1/g, '/').replace(/~0/g, '~'))) {
        if (Array.isArray(node)) node = node[Number(part)];
        else if (node && typeof node === 'object') node = node[part];
        else return null;
    }
    return typeof node === 'string' ? node : null;
}

/** Problems with a form's calculated fields (backend `calculated_field_problems`). */
/** Most calculated fields one form may have (backend MAX_CALCULATED_FIELDS). */
export const MAX_CALCULATED_FIELDS = 50;

/** Calculations of a page-based form that are not directly on a page (backend `_misplaced_calculations`). */
function misplacedCalculations(doc: FormDoc): FormField[] {
    const top = (doc.fields ?? []) as FormField[];
    if (!top.some(isSlide)) return [];
    const onPages = new Set<FormField>();
    for (const page of top) if (isSlide(page)) for (const field of (page.properties?.fields as FormField[] | undefined) ?? []) onPages.add(field);
    const misplaced: FormField[] = [];
    const pending = [...top];
    while (pending.length) {
        const field = pending.pop()!;
        if (!field) continue;
        if (isCalculated(field) && !onPages.has(field)) misplaced.push(field);
        pending.push(...(((field.properties?.fields as FormField[] | undefined) ?? []) as FormField[]));
    }
    return misplaced;
}

export function calculationProblems(doc: FormDoc): CalculationProblem[] {
    const problems: CalculationProblem[] = misplacedCalculations(doc).map((field) => ({
        fieldId: String(field.id ?? ''),
        path: '',
        message: `'${calcTitle(field)}' must be on a page: calculations cannot be placed inside a group or in a form without pages.`
    }));
    const calcs = pageFields(doc).filter(isCalculated);
    if (!calcs.length) return problems;
    if (calcs.length > MAX_CALCULATED_FIELDS) problems.push({ fieldId: '', path: '', message: `A form can have at most ${MAX_CALCULATED_FIELDS} calculated fields; this one has ${calcs.length}.` });
    const known = variableKeys(doc);
    const internal = new Set(
        pageFields(doc)
            .filter((f) => f.internal && f.id)
            .map((f) => String(f.id))
    );
    const ids = new Set(calcs.filter((f) => f.id).map((f) => String(f.id)));
    const byId = new Map(calcs.map((f) => [String(f.id), f]));
    const edges = new Map<string, string[]>();
    for (const field of calcs) {
        const id = String(field.id ?? '');
        if ((field.validations as any)?.required) problems.push({ fieldId: id, path: '', message: `'${calcTitle(field)}' is a calculation: it is computed, never answered, so it cannot be required.` });
        if (field.internal) {
            problems.push({ fieldId: id, path: '', message: `The calculation '${calcTitle(field)}' cannot be an internal field: it is computed from the respondent's answers.` });
            continue;
        }
        const ast = field.properties?.expression;
        if (ast === undefined || ast === null) continue;
        const structural = validateExpression(ast);
        if (structural.length) {
            for (const p of structural) problems.push({ fieldId: id, path: p.path, message: `'${calcTitle(field)}': ${p.message}` });
            continue;
        }
        for (const p of validateExpression(ast, { knownVariables: known })) {
            const key = varAt(ast, p.path);
            const message = key !== null && internal.has(key) ? `'${calcTitle(field)}' uses an internal field — respondents never answer internal fields, so a calculation cannot use them.` : `'${calcTitle(field)}' uses an unknown field or hidden field.`;
            problems.push({ fieldId: id, path: p.path, message });
        }
        const refs = expressionVariables(ast).filter((key) => ids.has(key));
        if (refs.length) edges.set(id, refs);
    }
    const cycle = findCycle(edges);
    if (cycle) {
        const names = cycle.filter((key) => byId.has(key)).map((key) => calcTitle(byId.get(key)!));
        problems.push({ fieldId: cycle[0], path: '', message: `Calculations cannot depend on each other in a circle (${[...names, ...names.slice(0, 1)].map((n) => `'${n}'`).join(' → ')}).` });
    }
    return problems;
}

/** An op's refusal message for a problem (backend `_calculation_message`). */
export const calculationMessage = (problem: CalculationProblem): string => `${problem.message}${problem.path ? ` (expression node '${problem.path}')` : ''}`;

/** The first calculation problem of `after` that `before` did not have. */
export function newCalculationProblem(before: FormDoc, after: FormDoc): string | null {
    if (!hasCalculations(after)) return null;
    const known = new Set(calculationProblems(before).map(calculationMessage));
    for (const problem of calculationProblems(after).map(calculationMessage)) if (!known.has(problem)) return problem;
    return null;
}

export interface CalculationSpec {
    expression?: unknown;
    format?: Record<string, unknown> | null;
    hiddenFromRespondents?: boolean | null;
    unansweredAsZero?: boolean | null;
}

const LABELS: Record<string, string> = { expression: 'formula', format: 'format', hiddenFromRespondents: 'visibility', unansweredAsZero: 'unanswered as 0' };

/**
 * Set a calculated field's expression, format, visibility and "unanswered
 * as 0" (only the ones given) on `properties` (backend `_set_calculation`).
 * Returns the change fragments.
 */
export function setCalculation(type: string, properties: Record<string, any>, spec: CalculationSpec): string[] {
    const given = (['expression', 'format', 'hiddenFromRespondents', 'unansweredAsZero'] as const).filter((key) => spec[key] !== undefined && spec[key] !== null);
    if (!given.length) return [];
    if (type !== FieldTypes.CALCULATED) throw new OpError(`${given.join(', ')}: only calculated fields have these.`);
    if (spec.expression != null) {
        const problems = validateExpression(spec.expression);
        if (problems.length) throw new OpError(`The expression is not valid at '${problems[0].path || '/'}': ${problems[0].message}`);
        properties.expression = spec.expression;
    }
    if (spec.format != null) properties.format = Object.fromEntries(Object.entries(spec.format).filter(([, v]) => v !== null && v !== undefined));
    if (spec.hiddenFromRespondents != null) {
        if (spec.hiddenFromRespondents) properties.hiddenFromRespondents = true;
        else delete properties.hiddenFromRespondents;
    }
    if (spec.unansweredAsZero != null) properties.unansweredAsZero = spec.unansweredAsZero;
    return given.map((key) => LABELS[key]);
}

export const REQUIRED_CALCULATION_MESSAGE = 'A calculation is computed, never answered, so it cannot be required.';
