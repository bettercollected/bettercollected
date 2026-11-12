/**
 * Conditions on answers ("answer filters") of a report: which responses it is about, by
 * what they answered. A condition is a question, an operator the question's kind takes and
 * a value that is an option id of the question, a number, a yes/no or a date, never text a
 * respondent wrote. The checks here mirror the server's (`services/reporting/definition.py`),
 * which decides: they keep a malformed address or a stale view from being sent.
 *
 * They live in the address like the cards (`where`, base64url of compact JSON: question keys,
 * operators, option ids, numbers and dates), so Back, a shared link and a saved view carry
 * them; reading an address never throws.
 */
import { CLAUSES_MAX, ReportCatalogue, ReportClause, ReportField, fieldOf, fromBase64Url, toBase64Url } from '@app/utils/report';
import { Translate, numberFormat } from '@app/utils/report-view';

export const NO_VALUE_OPS = ['is_empty', 'is_not_empty'];
export const LIST_OPS = ['any_of', 'has_any', 'has_all'];
export const PAIR_OPS = ['between'];
const ALL_OPS = ['is', 'is_not', 'any_of', 'has_any', 'has_all', '=', '!=', '>', '>=', '<', '<=', 'between', 'before', 'after', ...NO_VALUE_OPS];

const MAX_PARAM = 6000;
const FIELD_KEY = /^q:[\w.:-]{1,100}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const NUMBER_LIMIT = 10 ** 15;
const VALUE_LENGTH = 100;
const VALUES_MAX = 20;

type Scalar = boolean | number | string;

const isScalar = (value: unknown): value is Scalar => typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value)) || (typeof value === 'string' && value.length <= VALUE_LENGTH);

function cleanClause(raw: unknown): ReportClause | undefined {
    if (!raw || typeof raw !== 'object') return undefined;
    const clause = raw as Record<string, unknown>;
    if (typeof clause.field !== 'string' || !FIELD_KEY.test(clause.field)) return undefined;
    if (typeof clause.op !== 'string' || !ALL_OPS.includes(clause.op)) return undefined;
    const result: ReportClause = { field: clause.field, op: clause.op };
    if (clause.value === undefined) return result;
    if (Array.isArray(clause.value)) {
        if (clause.value.length > VALUES_MAX || !clause.value.every((item) => isScalar(item) && typeof item !== 'boolean')) return undefined;
        result.value = clause.value as Array<number | string>;
    } else if (isScalar(clause.value)) {
        result.value = clause.value;
    } else return undefined;
    return result;
}

/** The conditions an address carries, or undefined when it carries none or they are malformed. */
export function parseWhereParam(value: string | null | undefined): ReportClause[] | undefined {
    if (!value || value.length > MAX_PARAM) return undefined;
    try {
        const raw = JSON.parse(fromBase64Url(value));
        if (!Array.isArray(raw) || raw.length < 1 || raw.length > CLAUSES_MAX) return undefined;
        const clauses: ReportClause[] = [];
        for (const item of raw) {
            const clause = cleanClause(item);
            if (!clause) return undefined;
            clauses.push(clause);
        }
        return clauses;
    } catch {
        return undefined;
    }
}

export function whereParam(clauses: ReportClause[]): string {
    return toBase64Url(JSON.stringify(clauses.map(({ field, op, value }) => ({ field, op, ...(value === undefined ? {} : { value }) }))));
}

const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= NUMBER_LIMIT;
const isDay = (value: unknown): value is string => typeof value === 'string' && DAY.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));

/** Why a condition cannot be asked for, or undefined when it can: its question is gone, or the operator or value does not suit it. */
export function clauseProblem(clause: ReportClause, catalogue: ReportCatalogue): 'unknown' | 'invalid' | undefined {
    const field = fieldOf(catalogue, clause.field);
    if (!field) return 'unknown';
    if (!(field.filterOps ?? []).includes(clause.op)) return 'invalid';
    const { op, value } = clause;
    if (NO_VALUE_OPS.includes(op)) return value === undefined ? undefined : 'invalid';
    if (value === undefined) return 'invalid';
    const options = new Set((field.options ?? []).map((option) => option.id));
    if (field.kind === 'choice' || field.kind === 'choices') {
        const many = LIST_OPS.includes(op);
        const ids = Array.isArray(value) ? value : [value];
        if (many !== Array.isArray(value) || ids.length < 1) return 'invalid';
        return ids.every((id) => typeof id === 'string' && options.has(id)) ? undefined : 'invalid';
    }
    if (op === 'is') return typeof value === 'boolean' ? undefined : 'invalid';
    if (field.kind === 'date') {
        if (op === 'between') return Array.isArray(value) && value.length === 2 && value.every(isDay) && value[0] <= value[1] ? undefined : 'invalid';
        return isDay(value) ? undefined : 'invalid';
    }
    if (op === 'between') return Array.isArray(value) && value.length === 2 && value.every(isNumber) && (value[0] as number) <= (value[1] as number) ? undefined : 'invalid';
    return isNumber(value) ? undefined : 'invalid';
}

/** The operators a question's kind takes (what the server's catalogue says), with the questions that take any. */
export function filterableFields(catalogue: ReportCatalogue): ReportField[] {
    return catalogue.fields.filter((field) => (field.filterOps ?? []).length > 0);
}

/** A condition to start from for a question: its first operator, with the first option or a blank value. */
export function blankClause(field: ReportField): ReportClause {
    const op = (field.filterOps ?? [])[0] ?? 'is';
    return withOp({ field: field.key, op }, field);
}

/** The condition with another operator, its value reset to one that suits it. */
export function withOp(clause: ReportClause, field: ReportField, op: string = clause.op): ReportClause {
    const next: ReportClause = { field: clause.field, op };
    if (NO_VALUE_OPS.includes(op)) return next;
    const first = field.options?.[0]?.id;
    if (field.kind === 'choice' || field.kind === 'choices') {
        next.value = LIST_OPS.includes(op) ? (first ? [first] : []) : (first ?? '');
    } else if (op === 'is') {
        next.value = true;
    } else if (field.kind === 'date') {
        next.value = op === 'between' ? ['', ''] : '';
    } else {
        next.value = op === 'between' ? [0, 0] : 0;
    }
    return next;
}

/** One condition as a sentence for a chip: "Which team are you in? is North". */
export function describeClause(clause: ReportClause, catalogue: ReportCatalogue, t: Translate, locale: string): string {
    const field = fieldOf(catalogue, clause.field);
    const subject = field?.label ?? clause.field;
    const op = t(`REPORT.OP.${clause.op}`);
    if (NO_VALUE_OPS.includes(clause.op)) return `${subject} ${op}`;
    const numbers = numberFormat(locale);
    const day = (value: unknown) => {
        const parts = String(value).split('-').map(Number);
        try {
            return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])));
        } catch {
            return String(value);
        }
    };
    const one = (value: unknown): string => {
        if (typeof value === 'boolean') return t(`REPORT.GROUP.${value ? 'yes' : 'no'}`);
        if (field && (field.kind === 'choice' || field.kind === 'choices')) return field.options?.find((option) => option.id === value)?.label ?? String(value);
        if (field?.kind === 'date') return day(value);
        return typeof value === 'number' ? numbers.format(value) : String(value);
    };
    const list = Array.isArray(clause.value) ? clause.value : [clause.value];
    const text = clause.op === 'between' ? `${one(list[0])} – ${one(list[1])}` : list.map(one).join(', ');
    return `${subject} ${op} ${text}`;
}
