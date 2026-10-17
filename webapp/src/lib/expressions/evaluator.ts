import { ExprNode, ExpressionError, MAX_INPUT_LIST_ITEMS, MAX_INPUT_STRING_LENGTH, MAX_STRING_LENGTH, argsOf, codePointLength, isOpNode, opOf } from '@app/lib/expressions/ast';
import { Dec } from '@app/lib/expressions/decimal';
import { validateExpression } from '@app/lib/expressions/validator';

/**
 * Expression evaluator (spec: docs/spec/expressions-v1.md). Total on user
 * data: a type error yields null, never an exception. Only a malformed AST
 * throws (`ExpressionError`). The Python twin lives in
 * common/common/expressions/evaluator.py; both run the shared corpus
 * docs/spec/expressions-v1.cases.json.
 */

/** A value going in (variables) or coming out of an expression. */
export type ExprValue = null | boolean | number | string | ExprValue[];

export interface EvalContext {
    /** The respondent's today as YYYY-MM-DD; `today()` is null without it. */
    today?: string | null;
}

/** Internal value: numbers are decimals; lists are one level deep. */
type Scalar = null | boolean | string | Dec;
type Value = Scalar | Scalar[];

const ASCII_TRIM = /^[ \t\n\r]+|[ \t\n\r]+$/g;
const ISO_DATE = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/;

function scalarFromInput(input: unknown): Scalar {
    if (input === null || input === undefined) return null;
    if (typeof input === 'boolean') return input;
    if (typeof input === 'string') return input.length <= MAX_INPUT_STRING_LENGTH || codePointLength(input) <= MAX_INPUT_STRING_LENGTH ? input : null;
    if (typeof input === 'number') return Dec.fromNumber(input);
    if (typeof input === 'bigint') return Dec.parse(input.toString()) ?? null;
    return null;
}

/**
 * Normalises a variable value. Over-cap input becomes null: a text over
 * MAX_INPUT_STRING_LENGTH code points, a list over MAX_INPUT_LIST_ITEMS items,
 * and anything nested deeper than one list level.
 */
function fromInput(input: unknown): Value {
    if (Array.isArray(input)) {
        if (input.length > MAX_INPUT_LIST_ITEMS) return null;
        return input.map((item) => (Array.isArray(item) ? null : scalarFromInput(item)));
    }
    return scalarFromInput(input);
}

function cap(text: string): string {
    if (text.length <= MAX_STRING_LENGTH) return text;
    if (codePointLength(text) <= MAX_STRING_LENGTH) return text;
    return Array.from(text).slice(0, MAX_STRING_LENGTH).join('');
}

/** Number coercion: numbers, and texts that are plain decimal numbers. */
function toNum(value: Value): Dec | null {
    if (value instanceof Dec) return value;
    if (typeof value === 'string') {
        const parsed = Dec.parse(value.replace(ASCII_TRIM, ''));
        return parsed ?? null;
    }
    return null;
}

function isNumeric(value: Value): boolean {
    return value instanceof Dec || (typeof value === 'string' && toNum(value) !== null);
}

/** Text coercion (concat and display). */
function toText(value: Value): string {
    if (value === null) return '';
    if (Array.isArray(value))
        return value
            .map((item) => toText(item))
            .filter((text) => text !== '')
            .join(', ');
    if (value instanceof Dec) return value.toString();
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    return value;
}

function truthy(value: Value): boolean {
    if (value === null || value === false || value === '') return false;
    if (value instanceof Dec) return !value.isZero();
    if (Array.isArray(value)) return value.length > 0;
    return true;
}

function compareCodePoints(a: string, b: string): number {
    const ia = a[Symbol.iterator]();
    const ib = b[Symbol.iterator]();
    for (;;) {
        const x = ia.next();
        const y = ib.next();
        if (x.done || y.done) return x.done && y.done ? 0 : x.done ? -1 : 1;
        const cx = x.value.codePointAt(0) as number;
        const cy = y.value.codePointAt(0) as number;
        if (cx !== cy) return cx < cy ? -1 : 1;
    }
}

function equals(a: Value, b: Value): boolean | null {
    if (Array.isArray(a) || Array.isArray(b)) return null;
    if (a === null || b === null) return a === b;
    if (a instanceof Dec || b instanceof Dec) {
        const x = toNum(a);
        const y = toNum(b);
        return x !== null && y !== null && x.cmp(y) === 0;
    }
    return a === b;
}

/** -1 / 0 / 1, or null when the two values can't be ordered. */
function order(a: Value, b: Value): number | null {
    if (Array.isArray(a) || Array.isArray(b)) return null;
    if (isNumeric(a) && isNumeric(b)) return (toNum(a) as Dec).cmp(toNum(b) as Dec);
    if (typeof a === 'string' && typeof b === 'string') return compareCodePoints(a, b);
    return null;
}

/** Arguments of an aggregate, flattened; null and empty text skipped. */
function aggregateItems(values: Value[]): Scalar[] {
    const items: Scalar[] = [];
    values.forEach((value) => {
        (Array.isArray(value) ? value : [value]).forEach((item) => {
            if (item !== null && item !== '') items.push(item);
        });
    });
    return items;
}

function aggregateNumbers(values: Value[]): Dec[] | null {
    const numbers: Dec[] = [];
    for (const item of aggregateItems(values)) {
        const n = toNum(item);
        if (n === null) return null;
        numbers.push(n);
    }
    return numbers;
}

function sumOf(numbers: Dec[]): Dec | null {
    let total: Dec | null = Dec.ZERO;
    for (const n of numbers) {
        total = (total as Dec).add(n);
        if (total === null) return null;
    }
    return total;
}

/** Day number of a valid YYYY-MM-DD date (proleptic Gregorian), else null. */
export function isoDayNumber(value: Value): number | null {
    if (typeof value !== 'string') return null;
    const match = ISO_DATE.exec(value);
    if (!match) return null;
    let year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    if (year < 1 || month < 1 || month > 12 || day < 1) return null;
    const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
    const monthDays = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
    if (day > monthDays) return null;
    year -= month <= 2 ? 1 : 0;
    const era = Math.floor(year / 400);
    const yearOfEra = year - era * 400;
    const dayOfYear = Math.floor((153 * (month + (month > 2 ? -3 : 9)) + 2) / 5) + day - 1;
    const dayOfEra = yearOfEra * 365 + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100) + dayOfYear;
    return era * 146097 + dayOfEra - 719468;
}

type Evaluate = (node: ExprNode) => Value;

const unaryNumber =
    (fn: (n: Dec) => Dec | null) =>
    (args: ExprNode[], ev: Evaluate): Value => {
        const n = toNum(ev(args[0]));
        return n === null ? null : fn(n);
    };

const comparison =
    (test: (order: number) => boolean) =>
    (args: ExprNode[], ev: Evaluate): Value => {
        const result = order(ev(args[0]), ev(args[1]));
        return result === null ? null : test(result);
    };

const foldNumbers =
    (fn: (a: Dec, b: Dec) => Dec | null) =>
    (args: ExprNode[], ev: Evaluate): Value => {
        let acc = toNum(ev(args[0]));
        for (let i = 1; i < args.length && acc !== null; i++) {
            const next = toNum(ev(args[i]));
            acc = next === null ? null : fn(acc, next);
        }
        return acc;
    };

const OPS: Record<string, (args: ExprNode[], ev: Evaluate, context: EvalContext) => Value> = {
    '+': foldNumbers((a, b) => a.add(b)),
    '*': foldNumbers((a, b) => a.mul(b)),
    '-': (args, ev) => {
        if (args.length === 1) return unaryNumber((n) => n.neg())(args, ev);
        return foldNumbers((a, b) => a.sub(b))(args, ev);
    },
    '/': foldNumbers((a, b) => a.div(b)),
    '%': foldNumbers((a, b) => a.mod(b)),
    min: (args, ev) => {
        const numbers = aggregateNumbers(args.map(ev));
        if (!numbers || numbers.length === 0) return null;
        return numbers.reduce((a, b) => (b.cmp(a) < 0 ? b : a));
    },
    max: (args, ev) => {
        const numbers = aggregateNumbers(args.map(ev));
        if (!numbers || numbers.length === 0) return null;
        return numbers.reduce((a, b) => (b.cmp(a) > 0 ? b : a));
    },
    round: (args, ev) => {
        const n = toNum(ev(args[0]));
        if (n === null) return null;
        if (args.length < 2) return n.round(0);
        const digits = toNum(ev(args[1]));
        const places = digits?.toInteger();
        if (places === undefined) return null;
        return n.round(Math.min(Math.max(places, -16), 15));
    },
    floor: unaryNumber((n) => n.round(0, 'floor')),
    ceil: unaryNumber((n) => n.round(0, 'ceil')),
    abs: unaryNumber((n) => n.abs()),
    '==': (args, ev) => equals(ev(args[0]), ev(args[1])),
    '!=': (args, ev) => {
        const result = equals(ev(args[0]), ev(args[1]));
        return result === null ? null : !result;
    },
    '<': comparison((o) => o < 0),
    '<=': comparison((o) => o <= 0),
    '>': comparison((o) => o > 0),
    '>=': comparison((o) => o >= 0),
    and: (args, ev) => args.every((arg) => truthy(ev(arg))),
    or: (args, ev) => args.some((arg) => truthy(ev(arg))),
    not: (args, ev) => !truthy(ev(args[0])),
    if: (args, ev) => {
        let i = 0;
        for (; i + 1 < args.length; i += 2) {
            if (truthy(ev(args[i]))) return ev(args[i + 1]);
        }
        return i < args.length ? ev(args[i]) : null;
    },
    concat: (args, ev) => {
        let text = '';
        for (const arg of args) text = cap(text + toText(ev(arg)));
        return text;
    },
    length: (args, ev) => {
        const value = ev(args[0]);
        if (value === null || Array.isArray(value)) return null;
        return Dec.fromInt(codePointLength(toText(value)));
    },
    lower: (args, ev) => {
        const value = ev(args[0]);
        if (value === null || Array.isArray(value)) return null;
        return cap(toText(value).toLowerCase());
    },
    upper: (args, ev) => {
        const value = ev(args[0]);
        if (value === null || Array.isArray(value)) return null;
        return cap(toText(value).toUpperCase());
    },
    contains: (args, ev) => {
        const haystack = ev(args[0]);
        const needle = ev(args[1]);
        if (Array.isArray(needle)) return null;
        if (haystack === null || needle === null) return false;
        const target = toText(needle);
        if (Array.isArray(haystack)) return haystack.some((item) => item !== null && toText(item) === target);
        return toText(haystack).toLowerCase().includes(target.toLowerCase());
    },
    sum: (args, ev) => {
        const numbers = aggregateNumbers(args.map(ev));
        return numbers === null ? null : sumOf(numbers);
    },
    count: (args, ev) => Dec.fromInt(aggregateItems(args.map(ev)).length),
    avg: (args, ev) => {
        const numbers = aggregateNumbers(args.map(ev));
        if (!numbers || numbers.length === 0) return null;
        const total = sumOf(numbers);
        return total === null ? null : total.div(Dec.fromInt(numbers.length));
    },
    date_diff_days: (args, ev) => {
        const start = isoDayNumber(ev(args[0]));
        const end = isoDayNumber(ev(args[1]));
        return start === null || end === null ? null : Dec.fromInt(end - start);
    },
    today: (_args, _ev, context) => (isoDayNumber(context.today ?? null) === null ? null : (context.today as string))
};

function toOutput(value: Value): ExprValue {
    if (Array.isArray(value)) return value.map((item) => toOutput(item) as ExprValue);
    if (value instanceof Dec) return value.toNumber();
    if (typeof value === 'string') return cap(value);
    return value;
}

/**
 * Evaluate a well-formed AST against variables (keys as in the spec's
 * namespace) and a context. Throws `ExpressionError` only for a malformed AST.
 */
export function evaluateExpression(ast: unknown, variables: Record<string, unknown> = {}, context: EvalContext = {}): ExprValue {
    const problems = validateExpression(ast);
    if (problems.length) throw new ExpressionError(problems[0]);
    // Each variable is normalised once per evaluation, however often it is referenced.
    const normalised = new Map<string, Value>();
    const ev: Evaluate = (node) => {
        if (node === null || typeof node === 'boolean' || typeof node === 'string') return node;
        if (typeof node === 'number') return Dec.fromNumber(node);
        if (!isOpNode(node)) return null;
        const op = opOf(node);
        if (op === 'var') {
            const key = node.var as string;
            if (!Object.prototype.hasOwnProperty.call(variables, key)) return null;
            if (!normalised.has(key)) normalised.set(key, fromInput(variables[key]));
            return normalised.get(key) as Value;
        }
        return OPS[op](argsOf(node), ev, context);
    };
    return toOutput(ev(ast as ExprNode));
}

/** Display text of a result: plain decimals, "true"/"false", "" for null, lists joined with ", ". */
export function formatExpressionValue(value: ExprValue): string {
    return toText(fromInput(value));
}
