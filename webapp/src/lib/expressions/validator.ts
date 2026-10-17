import { ExprNode, ExpressionProblem, MAX_DEPTH, MAX_NODES, MAX_STRING_LENGTH, MAX_VAR_LENGTH, OPERATORS, codePointLength } from '@app/lib/expressions/ast';
import { Dec } from '@app/lib/expressions/decimal';

export interface ValidateOptions {
    /** When given, every `var` must name one of these keys. */
    knownVariables?: Iterable<string>;
}

function pointer(path: string, token: string | number): string {
    return `${path}/${String(token).replace(/~/g, '~0').replace(/\//g, '~1')}`;
}

/**
 * Check an AST against the v1 grammar and limits. Walks the tree depth-first
 * (pre-order) and returns problems in that order; stops at the node limit.
 * An empty list means the AST is well formed.
 */
export function validateExpression(ast: unknown, options: ValidateOptions = {}): ExpressionProblem[] {
    const problems: ExpressionProblem[] = [];
    const known = options.knownVariables ? new Set(options.knownVariables) : null;
    let nodes = 0;
    let stopped = false;

    const visit = (node: unknown, path: string, depth: number): void => {
        if (stopped) return;
        nodes += 1;
        if (nodes > MAX_NODES) {
            problems.push({ code: 'too_many_nodes', message: `An expression can have at most ${MAX_NODES} parts.`, path });
            stopped = true;
            return;
        }
        if (depth > MAX_DEPTH) {
            problems.push({ code: 'too_deep', message: `An expression can be nested at most ${MAX_DEPTH} levels deep.`, path });
            return;
        }
        if (node === null || typeof node === 'boolean') return;
        if (typeof node === 'number') {
            if (Dec.fromNumber(node) === null) problems.push({ code: 'invalid_literal', message: 'Numbers must be finite and smaller than 10^15.', path });
            return;
        }
        if (typeof node === 'string') {
            if (codePointLength(node) > MAX_STRING_LENGTH) problems.push({ code: 'string_too_long', message: `Text can be at most ${MAX_STRING_LENGTH} characters.`, path });
            return;
        }
        if (typeof node !== 'object' || Array.isArray(node)) {
            problems.push({ code: 'invalid_node', message: 'Expected a number, text, true, false, null or an operator object.', path });
            return;
        }
        const keys = Object.keys(node);
        if (keys.length !== 1) {
            problems.push({ code: 'invalid_node', message: 'An operator object must have exactly one key.', path });
            return;
        }
        const op = keys[0];
        const value = (node as Record<string, unknown>)[op];
        const opPath = pointer(path, op);
        if (op === 'var') {
            if (typeof value !== 'string' || value === '' || codePointLength(value) > MAX_VAR_LENGTH) {
                problems.push({ code: 'invalid_var', message: `A variable reference needs a name of 1 to ${MAX_VAR_LENGTH} characters.`, path: opPath });
            } else if (known && !known.has(value)) {
                problems.push({ code: 'unknown_variable', message: `Unknown variable "${value}".`, path: opPath });
            }
            return;
        }
        const arity = Object.prototype.hasOwnProperty.call(OPERATORS, op) ? OPERATORS[op] : undefined;
        if (!arity) {
            problems.push({ code: 'unknown_operator', message: `Unknown operator "${op}".`, path: opPath });
            return;
        }
        if (!Array.isArray(value)) {
            problems.push({ code: 'invalid_node', message: `The arguments of "${op}" must be a list.`, path: opPath });
            return;
        }
        const [min, max] = arity;
        if (value.length < min || value.length > max) {
            const expected = min === max ? `${min}` : max === Infinity ? `at least ${min}` : `${min} to ${max}`;
            problems.push({ code: 'arity', message: `"${op}" takes ${expected} argument${min === 1 && max === 1 ? '' : 's'}, got ${value.length}.`, path: opPath });
            return;
        }
        value.forEach((arg, index) => visit(arg, pointer(opPath, index), depth + 1));
    };

    visit(ast, '', 1);
    return problems;
}

/** True when `ast` is a well-formed expression. */
export function isValidExpression(ast: unknown, options?: ValidateOptions): ast is ExprNode {
    return validateExpression(ast, options).length === 0;
}
