/**
 * Shared shape of the formula syntax (spec: docs/spec/expressions-v1.md,
 * "Formula syntax"), used by the parser and the printer.
 *
 * Precedence, loosest first: or, and, not, comparisons, + -, * / %, unary -.
 */

export const PREC = {
    or: 1,
    and: 2,
    not: 3,
    compare: 4,
    add: 5,
    mul: 6,
    unary: 7,
    atom: 8
} as const;

/** Operators written infix, with their precedence. */
export const INFIX: Record<string, number> = {
    or: PREC.or,
    and: PREC.and,
    '==': PREC.compare,
    '!=': PREC.compare,
    '<': PREC.compare,
    '<=': PREC.compare,
    '>': PREC.compare,
    '>=': PREC.compare,
    '+': PREC.add,
    '-': PREC.add,
    '*': PREC.mul,
    '/': PREC.mul,
    '%': PREC.mul
};

/** Infix operators whose chains (`a + b + c`) become one variadic node. */
export const VARIADIC_INFIX = new Set(['+', '*', 'and', 'or']);

export const COMPARISONS = new Set(['==', '!=', '<', '<=', '>', '>=']);

/** Operators written as function calls: `round(x, 2)`. */
export const FUNCTIONS = new Set(['min', 'max', 'round', 'floor', 'ceil', 'abs', 'if', 'concat', 'length', 'lower', 'upper', 'contains', 'sum', 'count', 'avg', 'date_diff_days', 'today']);

/** Longest formula the parser accepts, in characters. */
export const MAX_FORMULA_LENGTH = 10000;
