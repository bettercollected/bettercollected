import { ExprNode, MAX_DEPTH, OPERATORS } from '@app/lib/expressions/ast';
import { Dec } from '@app/lib/expressions/decimal';
import { COMPARISONS, FUNCTIONS, MAX_FORMULA_LENGTH, VARIADIC_INFIX } from '@app/lib/expressions/syntax';
import { validateExpression } from '@app/lib/expressions/validator';

/**
 * Formula syntax → AST (spec: docs/spec/expressions-v1.md, "Formula syntax").
 *
 *   round(sum({Costs.amount}) * 1.21, 2)
 *   if({age} >= 18, "adult", "minor")
 *
 * Field references are written `{label or id}`; `resolveField` maps the text
 * between the braces to a variable key. Positions in errors are offsets into
 * the formula string (UTF-16 code units, as JS strings and text inputs count).
 */

export class FormulaError extends Error {
    readonly start: number;
    readonly end: number;

    constructor(message: string, start: number, end: number = start) {
        super(message);
        this.name = 'FormulaError';
        this.start = start;
        this.end = end;
    }
}

export interface ParseOptions {
    /** Map the text inside `{…}` to a variable key; null/undefined = unknown field. Defaults to the text itself. */
    resolveField?: (reference: string) => string | null | undefined;
}

type TokenType = 'number' | 'string' | 'ref' | 'name' | 'symbol' | 'end';

interface Token {
    type: TokenType;
    /** Number/symbol/name text, decoded string, or the reference text. */
    value: string;
    start: number;
    end: number;
}

const SYMBOLS = ['==', '!=', '<=', '>=', '<', '>', '+', '-', '*', '/', '%', '(', ')', ','];
const SPACE = /[ \t\n\r]/;
const DIGIT = /[0-9]/;
const NAME_START = /[A-Za-z_]/;
const NAME_PART = /[A-Za-z0-9_]/;
/**
 * Recursion guard, well below any JS stack limit: one AST level costs at most
 * a parenthesis plus a prefix operator. The AST limits apply after parsing.
 */
const MAX_NESTING = 3 * MAX_DEPTH;

function tokenize(text: string): Token[] {
    const tokens: Token[] = [];
    let i = 0;
    while (i < text.length) {
        const ch = text[i];
        if (SPACE.test(ch)) {
            i++;
            continue;
        }
        const start = i;
        if (DIGIT.test(ch) || (ch === '.' && DIGIT.test(text[i + 1] ?? ''))) {
            while (i < text.length && DIGIT.test(text[i])) i++;
            if (text[i] === '.') {
                i++;
                while (i < text.length && DIGIT.test(text[i])) i++;
            }
            if (i < text.length && (NAME_PART.test(text[i]) || text[i] === '.')) {
                throw new FormulaError(`Unexpected "${text[i]}" after a number.`, i, i + 1);
            }
            tokens.push({ type: 'number', value: text.slice(start, i), start, end: i });
            continue;
        }
        if (ch === '"') {
            i++;
            while (i < text.length && text[i] !== '"') {
                if (text[i] === '\\') i++;
                else if (text[i] === '\n' || text[i] === '\r') throw new FormulaError("Text can't contain a line break; write \\n instead.", i, i + 1);
                i++;
            }
            if (i >= text.length) throw new FormulaError('This text is missing its closing quote (").', start, text.length);
            i++;
            let decoded: string;
            try {
                decoded = JSON.parse(text.slice(start, i));
            } catch {
                throw new FormulaError('This text has an invalid escape or a tab; use \\" \\\\ \\n \\t or \\uXXXX.', start, i);
            }
            tokens.push({ type: 'string', value: decoded, start, end: i });
            continue;
        }
        if (ch === '{') {
            i++;
            let reference = '';
            while (i < text.length && text[i] !== '}') {
                if (text[i] === '\\' && i + 1 < text.length) i++;
                reference += text[i];
                i++;
            }
            if (i >= text.length) throw new FormulaError('This field reference is missing its closing "}".', start, text.length);
            i++;
            reference = reference.trim();
            if (!reference) throw new FormulaError('Empty field reference; write a field name between the braces.', start, i);
            tokens.push({ type: 'ref', value: reference, start, end: i });
            continue;
        }
        if (NAME_START.test(ch)) {
            while (i < text.length && NAME_PART.test(text[i])) i++;
            tokens.push({ type: 'name', value: text.slice(start, i), start, end: i });
            continue;
        }
        const symbol = SYMBOLS.find((s) => text.startsWith(s, i));
        if (symbol) {
            i += symbol.length;
            tokens.push({ type: 'symbol', value: symbol, start, end: i });
            continue;
        }
        if (ch === '=') throw new FormulaError('Use == to compare two values.', i, i + 1);
        if (ch === '&' || ch === '|' || ch === '!') throw new FormulaError(`Use the words and, or, not instead of "${ch}".`, i, i + 1);
        if (ch === "'") throw new FormulaError('Write text in double quotes ("…").', i, i + 1);
        throw new FormulaError(`Unexpected "${ch}".`, i, i + 1);
    }
    tokens.push({ type: 'end', value: '', start: text.length, end: text.length });
    return tokens;
}

function describe(token: Token): string {
    if (token.type === 'end') return 'the end of the formula';
    if (token.type === 'string') return 'text';
    if (token.type === 'ref') return `{${token.value}}`;
    return `"${token.value}"`;
}

function arityText(op: string): string {
    const [min, max] = OPERATORS[op];
    if (min === max) return `${min} argument${min === 1 ? '' : 's'}`;
    if (max === Infinity) return `at least ${min} argument${min === 1 ? '' : 's'}`;
    return `${min} to ${max} arguments`;
}

/** Parse a formula into an AST. Throws `FormulaError` with a position on any problem. */
export function parseFormula(text: string, options: ParseOptions = {}): ExprNode {
    if (text.length > MAX_FORMULA_LENGTH) throw new FormulaError(`A formula can be at most ${MAX_FORMULA_LENGTH} characters long.`, MAX_FORMULA_LENGTH, text.length);
    const resolve = options.resolveField ?? ((reference: string) => reference);
    const tokens = tokenize(text);
    let pos = 0;
    let nesting = 0;

    const peek = (): Token => tokens[pos];
    const next = (): Token => tokens[pos++];
    const isSymbol = (value: string): boolean => peek().type === 'symbol' && peek().value === value;
    const isWord = (word: string): boolean => peek().type === 'name' && peek().value.toLowerCase() === word;
    const enter = (token: Token): void => {
        nesting += 1;
        if (nesting > MAX_NESTING) throw new FormulaError('This formula is nested too deeply.', token.start, token.end);
    };

    /** Left-associative chain; `+ * and or` chains become one variadic node. */
    const chain = (parseOperand: () => ExprNode, match: () => string | null): ExprNode => {
        let left = parseOperand();
        let leftOp: string | null = null;
        for (let op = match(); op; op = match()) {
            next();
            const right = parseOperand();
            if (leftOp === op && VARIADIC_INFIX.has(op)) {
                ((left as Record<string, ExprNode[]>)[op] as ExprNode[]).push(right);
            } else {
                left = { [op]: [left, right] };
            }
            leftOp = op;
        }
        return left;
    };

    const parseExpression = (): ExprNode => parseOr();
    const parseOr = (): ExprNode => chain(parseAnd, () => (isWord('or') ? 'or' : null));
    const parseAnd = (): ExprNode => chain(parseNot, () => (isWord('and') ? 'and' : null));
    const parseNot = (): ExprNode => {
        if (isWord('not')) {
            const token = next();
            enter(token);
            const operand = parseNot();
            nesting -= 1;
            return { not: [operand] };
        }
        return parseComparison();
    };
    const parseComparison = (): ExprNode => {
        const left = parseAdditive();
        const token = peek();
        if (token.type !== 'symbol' || !COMPARISONS.has(token.value)) return left;
        next();
        const right = parseAdditive();
        const after = peek();
        if (after.type === 'symbol' && COMPARISONS.has(after.value)) {
            throw new FormulaError('Comparisons can\'t be chained; combine them with "and".', after.start, after.end);
        }
        return { [token.value]: [left, right] };
    };
    const parseAdditive = (): ExprNode => chain(parseMultiplicative, () => (isSymbol('+') ? '+' : isSymbol('-') ? '-' : null));
    const parseMultiplicative = (): ExprNode => chain(parseUnary, () => (isSymbol('*') ? '*' : isSymbol('/') ? '/' : isSymbol('%') ? '%' : null));
    const parseUnary = (): ExprNode => {
        if (!isSymbol('-')) return parsePrimary();
        const token = next();
        if (peek().type === 'number') return -numberLiteral(next()) || 0;
        enter(token);
        const operand = parseUnary();
        nesting -= 1;
        return { '-': [operand] };
    };

    const numberLiteral = (token: Token): number => {
        const value = Dec.parse(token.value);
        if (!value) throw new FormulaError('This number is too large; numbers must be smaller than 10^15.', token.start, token.end);
        return value.toNumber();
    };

    const parseArguments = (name: Token, op: string): ExprNode[] => {
        const open = next(); // "("
        enter(open);
        const args: ExprNode[] = [];
        if (!isSymbol(')')) {
            for (;;) {
                args.push(parseExpression());
                if (isSymbol(',')) {
                    next();
                    continue;
                }
                break;
            }
        }
        if (!isSymbol(')')) {
            const token = peek();
            throw new FormulaError(`Expected "," or ")" in ${op}(…), found ${describe(token)}.`, token.start, token.end);
        }
        const close = next();
        nesting -= 1;
        const [min, max] = OPERATORS[op];
        if (args.length < min || args.length > max) {
            throw new FormulaError(`${op} takes ${arityText(op)}, got ${args.length}.`, name.start, close.end);
        }
        return args;
    };

    const parsePrimary = (): ExprNode => {
        const token = peek();
        switch (token.type) {
            case 'number':
                next();
                return numberLiteral(token);
            case 'string':
                next();
                return token.value;
            case 'ref': {
                next();
                const key = resolve(token.value);
                if (!key) throw new FormulaError(`Unknown field {${token.value}}.`, token.start, token.end);
                return { var: key };
            }
            case 'name': {
                next();
                const word = token.value.toLowerCase();
                if (word === 'true') return true;
                if (word === 'false') return false;
                if (word === 'null') return null;
                if (FUNCTIONS.has(word)) {
                    if (!isSymbol('(')) throw new FormulaError(`Expected "(" after ${word}.`, peek().start, peek().end);
                    return { [word]: parseArguments(token, word) };
                }
                if (word === 'and' || word === 'or' || word === 'not') throw new FormulaError(`Expected a value before "${token.value}".`, token.start, token.end);
                if (isSymbol('(')) throw new FormulaError(`Unknown function "${token.value}".`, token.start, token.end);
                throw new FormulaError(`Unknown name "${token.value}". Write field references in braces, like {${token.value}}, and text in quotes.`, token.start, token.end);
            }
            case 'symbol':
                if (token.value === '(') {
                    next();
                    enter(token);
                    const inner = parseExpression();
                    if (!isSymbol(')')) {
                        const found = peek();
                        throw new FormulaError(`Expected ")" to close the "(" at position ${token.start}, found ${describe(found)}.`, found.start, found.end);
                    }
                    next();
                    nesting -= 1;
                    return inner;
                }
                throw new FormulaError(`Expected a value, found ${describe(token)}.`, token.start, token.end);
            default:
                throw new FormulaError(text.trim() ? 'The formula ends too early; a value is missing.' : 'The formula is empty.', token.start, token.end);
        }
    };

    const ast = parseExpression();
    const rest = peek();
    if (rest.type !== 'end') throw new FormulaError(`Unexpected ${describe(rest)}; is an operator or a comma missing?`, rest.start, rest.end);
    const problems = validateExpression(ast);
    if (problems.length) throw new FormulaError(problems[0].message, 0, text.length);
    return ast;
}
