/**
 * Conditions on answers ("answer filters") of a report: which responses it is about, by
 * what they answered. A condition is a question, an operator the question's kind takes and
 * a value that is an option id of the question, a number, a yes/no or a date, never text a
 * respondent wrote. The checks here mirror the server's (`services/reporting/definition.py`),
 * which decides: they keep a stale view or a hand-built condition from being sent.
 *
 * They are never put in an address: a number or a date asked about is an answer value (a birth year, a
 * salary, an appointment) and an address reaches browser history, logs and Referer headers. The page
 * keeps them in memory, and a saved view carries them server-side.
 */
import { ReportCatalogue, ReportClause, ReportField, fieldOf } from '@app/utils/report';
import { Translate, numberFormat } from '@app/utils/report-view';

export const NO_VALUE_OPS = ['is_empty', 'is_not_empty'];
export const LIST_OPS = ['any_of', 'has_any', 'has_all'];
export const PAIR_OPS = ['between'];
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const NUMBER_LIMIT = 10 ** 15;

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
