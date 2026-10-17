import { ExprNode, argsOf, isOpNode, opOf } from '@app/lib/expressions/ast';
import { Dec } from '@app/lib/expressions/decimal';
import { INFIX, PREC, VARIADIC_INFIX } from '@app/lib/expressions/syntax';

/**
 * AST → formula syntax, the inverse of `parseFormula`: for every well-formed
 * AST, `parseFormula(printFormula(ast))` gives the same AST back (with the
 * same label mapping). Parentheses are added only where needed.
 */

export interface PrintOptions {
    /** Map a variable key to the label shown between braces. Defaults to the key itself. */
    fieldLabel?: (key: string) => string | null | undefined;
}

function numberText(value: number): string {
    return Dec.fromNumber(value)?.toString() ?? String(value);
}

function precedence(node: ExprNode): number {
    if (typeof node === 'number') return node < 0 ? PREC.unary : PREC.atom;
    if (!isOpNode(node)) return PREC.atom;
    const op = opOf(node);
    if (op === '-' && argsOf(node).length === 1) return PREC.unary;
    if (op === 'not') return PREC.not;
    return INFIX[op] ?? PREC.atom;
}

/** Print an AST as a formula. Assumes a well-formed AST (see validateExpression). */
export function printFormula(ast: ExprNode, options: PrintOptions = {}): string {
    const label = options.fieldLabel ?? ((key: string) => key);

    const wrap = (node: ExprNode, parens: boolean): string => (parens ? `(${print(node)})` : print(node));

    const print = (node: ExprNode): string => {
        if (node === null) return 'null';
        if (typeof node === 'boolean') return node ? 'true' : 'false';
        if (typeof node === 'number') return numberText(node);
        if (typeof node === 'string') return JSON.stringify(node);
        const op = opOf(node);
        if (op === 'var') {
            const key = node.var as string;
            const text = label(key) ?? key;
            return `{${text.replace(/\\/g, '\\\\').replace(/\}/g, '\\}')}}`;
        }
        const args = argsOf(node);
        if (op === '-' && args.length === 1) {
            const operand = args[0];
            // `-(5)` keeps a negated literal apart from the literal -5; `-(-x)` avoids "--".
            const negated = isOpNode(operand) && opOf(operand) === '-' && argsOf(operand).length === 1;
            const parens = typeof operand === 'number' || negated || precedence(operand) < PREC.unary;
            return `-${wrap(operand, parens)}`;
        }
        if (op === 'not') {
            return `not ${wrap(args[0], precedence(args[0]) < PREC.not)}`;
        }
        const level = INFIX[op];
        if (level !== undefined) {
            return args
                .map((arg, index) => {
                    const argLevel = precedence(arg);
                    if (level === PREC.compare) return wrap(arg, argLevel <= level);
                    if (index > 0) return wrap(arg, argLevel <= level);
                    // A left operand that is the same variadic operator would merge on re-parse.
                    const merges = VARIADIC_INFIX.has(op) && isOpNode(arg) && opOf(arg) === op;
                    return wrap(arg, argLevel < level || merges);
                })
                .join(` ${op} `);
        }
        return `${op}(${args.map((arg) => print(arg)).join(', ')})`;
    };

    return print(ast);
}
