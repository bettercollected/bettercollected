import { readFileSync } from 'fs';
import { resolve } from 'path';

import { ExprNode } from '@app/lib/expressions/ast';
import { evaluateExpression } from '@app/lib/expressions/evaluator';
import { FormulaError, parseFormula } from '@app/lib/expressions/parser';
import { printFormula } from '@app/lib/expressions/printer';

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../../docs/spec/expressions-v1.cases.json'), 'utf-8')) as {
    cases: Array<{ name: string; ast: ExprNode; error?: string }>;
};

// A form with a repeating group "Costs" (id g1) whose question "amount" is c1.
const LABELS: Record<string, string> = { age: 'f_age', 'Costs.amount': 'g1.c1', 'First name': 'f_name', 'a}b': 'f_brace' };
const IDS = Object.fromEntries(Object.entries(LABELS).map(([label, id]) => [id, label]));
const resolveField = (reference: string) => LABELS[reference];
const fieldLabel = (key: string) => IDS[key];

function parseError(text: string, options = {}): FormulaError {
    try {
        parseFormula(text, options);
    } catch (error) {
        if (error instanceof FormulaError) return error;
        throw error;
    }
    throw new Error(`expected "${text}" to fail`);
}

describe('parseFormula', () => {
    it('parses the documented examples', () => {
        expect(parseFormula('round(sum({Costs.amount}) * 1.21, 2)', { resolveField })).toEqual({ round: [{ '*': [{ sum: [{ var: 'g1.c1' }] }, 1.21] }, 2] });
        expect(parseFormula('if({age} >= 18, "adult", "minor")', { resolveField })).toEqual({ if: [{ '>=': [{ var: 'f_age' }, 18] }, 'adult', 'minor'] });
    });

    it('evaluates a parsed formula', () => {
        const ast = parseFormula('round(sum({Costs.amount}) * 1.21, 2)', { resolveField });
        expect(evaluateExpression(ast, { 'g1.c1': [100, 20, null] })).toBe(145.2);
    });

    it.each([
        ['1 + 2 * 3', { '+': [1, { '*': [2, 3] }] }],
        ['(1 + 2) * 3', { '*': [{ '+': [1, 2] }, 3] }],
        ['1 + 2 + 3', { '+': [1, 2, 3] }],
        ['(1 + 2) + 3', { '+': [{ '+': [1, 2] }, 3] }],
        ['1 - 2 - 3', { '-': [{ '-': [1, 2] }, 3] }],
        ['1 - (2 - 3)', { '-': [1, { '-': [2, 3] }] }],
        ['1 - 2 + 3', { '+': [{ '-': [1, 2] }, 3] }],
        ['8 / 4 % 3', { '%': [{ '/': [8, 4] }, 3] }],
        ['-5', -5],
        ['-(5)', { '-': [5] }],
        ['-{x}', { '-': [{ var: 'x' }] }],
        ['2 * -3', { '*': [2, -3] }],
        ['-0', 0],
        ['.5 + 1.', { '+': [0.5, 1] }],
        ['{a} == 1 or {b} != 2 and {c} < 3', { or: [{ '==': [{ var: 'a' }, 1] }, { and: [{ '!=': [{ var: 'b' }, 2] }, { '<': [{ var: 'c' }, 3] }] }] }],
        ['not {a} and {b}', { and: [{ not: [{ var: 'a' }] }, { var: 'b' }] }],
        ['not ({a} and {b})', { not: [{ and: [{ var: 'a' }, { var: 'b' }] }] }],
        ['not {a} == 1', { not: [{ '==': [{ var: 'a' }, 1] }] }],
        ['{a} and {b} and {c}', { and: [{ var: 'a' }, { var: 'b' }, { var: 'c' }] }],
        ['ROUND(1.5) + Sum(1, 2)', { '+': [{ round: [1.5] }, { sum: [1, 2] }] }],
        ['TRUE or False or NULL', { or: [true, false, null] }],
        ['today()', { today: [] }],
        ['concat("a\\"b", "\\n", "é😀")', { concat: ['a"b', '\n', 'é😀'] }],
        ['{a\\}b} + { spaced name }', { '+': [{ var: 'a}b' }, { var: 'spaced name' }] }],
        ['  1\n+\t2  ', { '+': [1, 2] }]
    ])('parses %s', (text, ast) => {
        expect(parseFormula(text)).toEqual(ast);
    });

    it.each([
        ['', 'The formula is empty.', 0],
        ['1 +', 'The formula ends too early; a value is missing.', 3],
        ['{age} = 18', 'Use == to compare two values.', 6],
        ['{a} && {b}', 'Use the words and, or, not instead of "&".', 4],
        ["'x'", 'Write text in double quotes ("…").', 0],
        ['1 < 2 < 3', 'Comparisons can\'t be chained; combine them with "and".', 6],
        ['pow(2, 3)', 'Unknown function "pow".', 0],
        ['age + 1', 'Unknown name "age". Write field references in braces, like {age}, and text in quotes.', 0],
        ['round(1, 2, 3)', 'round takes 1 to 2 arguments, got 3.', 0],
        ['today(1)', 'today takes 0 arguments, got 1.', 0],
        ['(1 + 2', 'Expected ")" to close the "(" at position 0, found the end of the formula.', 6],
        ['round(1 2)', 'Expected "," or ")" in round(…), found "2".', 8],
        ['1 2', 'Unexpected "2"; is an operator or a comma missing?', 2],
        ['"abc', 'This text is missing its closing quote (").', 0],
        ['"a\\qb"', 'This text has an invalid escape or a tab; use \\" \\\\ \\n \\t or \\uXXXX.', 0],
        ['{abc', 'This field reference is missing its closing "}".', 0],
        ['{ }', 'Empty field reference; write a field name between the braces.', 0],
        ['1.2.3', 'Unexpected "." after a number.', 3],
        ['12abc', 'Unexpected "a" after a number.', 2],
        ['1000000000000000', 'This number is too large; numbers must be smaller than 10^15.', 0],
        ['round', 'Expected "(" after round.', 5],
        ['1 + and', 'Expected a value before "and".', 4],
        ['1 # 2', 'Unexpected "#".', 2]
    ])('reports %j', (text, message, start) => {
        const error = parseError(text);
        expect(error.message).toBe(message);
        expect(error.start).toBe(start);
    });

    it('reports unknown fields at their position', () => {
        const error = parseError('{age} + {Height}', { resolveField });
        expect(error.message).toBe('Unknown field {Height}.');
        expect([error.start, error.end]).toEqual([8, 16]);
    });

    it('applies the AST limits', () => {
        const tooMany = Array.from({ length: 501 }, () => '1').join(' + ');
        expect(parseError(tooMany).message).toBe('An expression can have at most 500 parts.');
        const tooDeep = `${'abs('.repeat(32)}1${')'.repeat(32)}`;
        expect(parseError(tooDeep).message).toBe('An expression can be nested at most 32 levels deep.');
        expect(parseError(`${'('.repeat(4000)}1${')'.repeat(4000)}`).message).toBe('This formula is nested too deeply.');
        expect(parseError('1'.repeat(10001)).message).toBe('A formula can be at most 10000 characters long.');
    });
});

describe('printFormula', () => {
    it('prints labels in braces and escapes them', () => {
        const ast = { round: [{ '*': [{ sum: [{ var: 'g1.c1' }] }, 1.21] }, 2] };
        expect(printFormula(ast, { fieldLabel })).toBe('round(sum({Costs.amount}) * 1.21, 2)');
        expect(printFormula({ var: 'f_brace' }, { fieldLabel })).toBe('{a\\}b}');
        expect(printFormula({ var: 'unknown_id' }, { fieldLabel })).toBe('{unknown_id}');
    });

    it('prints numbers as plain decimals and texts as JSON strings', () => {
        expect(printFormula({ '+': [1e-7, 1e14] })).toBe('0.0000001 + 100000000000000');
        expect(printFormula({ concat: ['say "hi"\n', 'é'] })).toBe('concat("say \\"hi\\"\\n", "é")');
    });

    it.each([
        'round(sum({Costs.amount}) * 1.21, 2)',
        'if({age} >= 18, "adult", "minor")',
        '1 + 2 * 3',
        '(1 + 2) * 3',
        '(1 + 2) + 3',
        '1 - (2 - 3)',
        '-(5) + -5 - -{age}',
        '-(-{age})',
        '-(1 + 2)',
        'not {age} and ({age} or not {First name} == "x")',
        '(not {age}) == true',
        '({age} > 1) == ({age} < 5)',
        'if({age} < 0, null, {age} >= 18, "adult", "minor")',
        'date_diff_days({First name}, today()) / 365.25',
        'concat("Hello, ", {First name}, "!")',
        '{a\\}b} % 2'
    ])('round-trips %s', (text) => {
        const ast = parseFormula(text, { resolveField: (ref) => resolveField(ref) ?? ref });
        expect(printFormula(ast, { fieldLabel })).toBe(text);
    });

    it('round-trips every valid corpus AST', () => {
        const valid = corpus.cases.filter((c) => !c.error);
        expect(valid.length).toBeGreaterThan(100);
        valid.forEach(({ name, ast }) => {
            const text = printFormula(ast);
            expect({ name, ast: parseFormula(text) }).toEqual({ name, ast });
        });
    });

    it('round-trips nested variadic and unary shapes', () => {
        const asts: ExprNode[] = [
            { '+': [{ '+': [1, 2] }, { '+': [3, 4] }] },
            { '*': [{ '*': [1, 2] }, 3, { '-': [4] }] },
            { and: [{ and: [true, false] }, { or: [true, { or: [false, true] }] }] },
            { '-': [{ '-': [{ '-': [-1] }] }] },
            { not: [{ not: [{ '<': [{ '-': [1, 2] }, { '-': [3] }] }] }] },
            { '==': [{ '==': [1, 1] }, true] },
            { '-': [{ '*': [2, 3] }] },
            { '/': [1, { '/': [2, 3] }] },
            { '%': [{ '+': [1, 2] }, -3] }
        ];
        asts.forEach((ast) => expect(parseFormula(printFormula(ast))).toEqual(ast));
    });
});
