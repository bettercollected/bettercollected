/**
 * Expression AST (spec: docs/spec/expressions-v1.md).
 *
 * A node is a literal (number, string, boolean, null) or an operator object
 * with exactly one key: `{"op": [args...]}`. Variables are `{"var": "<key>"}`.
 */

export type Literal = number | string | boolean | null;
export type OpNode = { [op: string]: ExprNode[] | string };
export type ExprNode = Literal | OpNode;

/** Limits on the AST shape. */
export const MAX_DEPTH = 32;
export const MAX_NODES = 500;
/** Strings (literals and results) are at most this many characters (code points). */
export const MAX_STRING_LENGTH = 1000;
/** Variable keys are at most this many characters. */
export const MAX_VAR_LENGTH = 200;

/** Allowed argument counts: [min, max]; max `Infinity` = variadic. */
export const OPERATORS: Record<string, [number, number]> = {
    '+': [2, Infinity],
    '-': [1, 2],
    '*': [2, Infinity],
    '/': [2, 2],
    '%': [2, 2],
    min: [1, Infinity],
    max: [1, Infinity],
    round: [1, 2],
    floor: [1, 1],
    ceil: [1, 1],
    abs: [1, 1],
    '==': [2, 2],
    '!=': [2, 2],
    '<': [2, 2],
    '<=': [2, 2],
    '>': [2, 2],
    '>=': [2, 2],
    and: [2, Infinity],
    or: [2, Infinity],
    not: [1, 1],
    if: [2, Infinity],
    concat: [1, Infinity],
    length: [1, 1],
    lower: [1, 1],
    upper: [1, 1],
    contains: [2, 2],
    sum: [1, Infinity],
    count: [1, Infinity],
    avg: [1, Infinity],
    date_diff_days: [2, 2],
    today: [0, 0]
};

export type ExpressionErrorCode = 'invalid_node' | 'invalid_literal' | 'unknown_operator' | 'arity' | 'invalid_var' | 'unknown_variable' | 'string_too_long' | 'too_deep' | 'too_many_nodes';

export interface ExpressionProblem {
    code: ExpressionErrorCode;
    message: string;
    /** JSON Pointer to the node ("" is the root). */
    path: string;
}

/** Thrown by `evaluate` for a malformed AST, never for user data. */
export class ExpressionError extends Error {
    readonly code: ExpressionErrorCode;
    readonly path: string;

    constructor(problem: ExpressionProblem) {
        super(problem.message);
        this.name = 'ExpressionError';
        this.code = problem.code;
        this.path = problem.path;
    }
}

export function isOpNode(node: unknown): node is OpNode {
    return typeof node === 'object' && node !== null && !Array.isArray(node);
}

/** The single operator of an op node. */
export function opOf(node: OpNode): string {
    return Object.keys(node)[0];
}

/** Arguments of an op node (`var` has none in this sense). */
export function argsOf(node: OpNode): ExprNode[] {
    const value = node[opOf(node)];
    return Array.isArray(value) ? value : [];
}

/** Length in Unicode code points. */
export function codePointLength(text: string): number {
    let n = 0;
    for (let i = 0; i < text.length; i++) {
        const code = text.charCodeAt(i);
        if (code >= 0xd800 && code <= 0xdbff && i + 1 < text.length) {
            const next = text.charCodeAt(i + 1);
            if (next >= 0xdc00 && next <= 0xdfff) i++;
        }
        n++;
    }
    return n;
}
