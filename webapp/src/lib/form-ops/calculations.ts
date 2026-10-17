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

export function hasCalculations(doc: FormDoc): boolean {
    for (const page of (doc.fields ?? []) as FormField[]) {
        if (!page || typeof page !== 'object') continue;
        let has = pageHasCalculation.get(page);
        if (has === undefined) {
            has = ((page.properties?.fields as FormField[] | undefined) ?? []).some(isCalculated);
            pageHasCalculation.set(page, has);
        }
        if (has) return true;
    }
    return false;
}

/** Could an op from `before` to `after` have broken a calculation? (Only when either has one.) */
export const calculationsTouched = (before: FormDoc, after: FormDoc): boolean => before !== after && (hasCalculations(after) || hasCalculations(before));

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
export function calculationProblems(doc: FormDoc): CalculationProblem[] {
    const calcs = pageFields(doc).filter(isCalculated);
    if (!calcs.length) return [];
    const known = variableKeys(doc);
    const internal = new Set(
        pageFields(doc)
            .filter((f) => f.internal && f.id)
            .map((f) => String(f.id))
    );
    const ids = new Set(calcs.filter((f) => f.id).map((f) => String(f.id)));
    const byId = new Map(calcs.map((f) => [String(f.id), f]));
    const problems: CalculationProblem[] = [];
    const edges = new Map<string, string[]>();
    for (const field of calcs) {
        const id = String(field.id ?? '');
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
