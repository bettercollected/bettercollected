import { readFileSync } from 'fs';
import { resolve } from 'path';

import { ExpressionError } from '@app/lib/expressions/ast';
import { ExprValue, evaluateExpression, formatExpressionValue } from '@app/lib/expressions/evaluator';
import { isValidExpression, validateExpression } from '@app/lib/expressions/validator';

/**
 * The shared conformance corpus (also run by common/tests/test_expressions.py)
 * plus TS-specific checks.
 */

interface Case {
    name: string;
    ast: unknown;
    vars?: Record<string, unknown>;
    context?: { today?: string };
    expected?: ExprValue;
    error?: string;
}

const corpus = JSON.parse(readFileSync(resolve(__dirname, '../../../../docs/spec/expressions-v1.cases.json'), 'utf-8')) as { cases: Case[] };

const CASES = corpus.cases;

describe('expressions corpus', () => {
    it('has at least 150 uniquely named cases', () => {
        expect(CASES.length).toBeGreaterThanOrEqual(150);
        expect(new Set(CASES.map((c) => c.name)).size).toBe(CASES.length);
    });

    it.each(CASES.map((c) => [c.name, c] as const))('%s', (_name, testCase) => {
        const run = () => evaluateExpression(testCase.ast, testCase.vars ?? {}, testCase.context ?? {});
        if (testCase.error) {
            expect(run).toThrow(ExpressionError);
            try {
                run();
            } catch (error) {
                expect((error as ExpressionError).code).toBe(testCase.error);
            }
            return;
        }
        expect(run()).toStrictEqual(testCase.expected);
    });
});

describe('evaluateExpression', () => {
    it('returns plain numbers that print without float noise', () => {
        expect(evaluateExpression({ '+': [0.1, 0.2] })).toBe(0.3);
        expect(String(evaluateExpression({ '/': [2, 3] }))).toBe('0.666666666666667');
        expect(Object.is(evaluateExpression({ '-': [0] }), 0)).toBe(true);
    });

    it('treats non-JSON inputs as null', () => {
        expect(evaluateExpression({ var: 'x' }, { x: undefined })).toBeNull();
        expect(evaluateExpression({ var: 'x' }, { x: NaN })).toBeNull();
        expect(evaluateExpression({ var: 'x' }, { x: () => 1 })).toBeNull();
        expect(evaluateExpression({ var: 'x' }, { x: BigInt(12) })).toBe(12);
    });

    it('does not read inherited properties of the variables object', () => {
        const variables = Object.create({ inherited: 5 });
        expect(evaluateExpression({ var: 'inherited' }, variables)).toBeNull();
    });

    it('rejects a deeply nested AST without overflowing the stack', () => {
        let node: unknown = 1;
        for (let i = 0; i < 100000; i++) node = { '-': [node] };
        expect(() => evaluateExpression(node)).toThrow(ExpressionError);
    });
});

describe('validateExpression', () => {
    it('reports every problem with a JSON Pointer path', () => {
        const problems = validateExpression({ '+': [{ var: '' }, { '/': [1] }, { pow: [1, 2] }] });
        expect(problems.map((p) => [p.code, p.path])).toEqual([
            ['invalid_var', '/+/0/var'],
            ['arity', '/+/1/~1'],
            ['unknown_operator', '/+/2/pow']
        ]);
    });

    it('checks variables against known keys when given', () => {
        const ast = { '+': [{ var: 'a' }, { var: 'b' }] };
        expect(isValidExpression(ast, { knownVariables: ['a', 'b'] })).toBe(true);
        expect(validateExpression(ast, { knownVariables: new Set(['a']) }).map((p) => [p.code, p.path])).toEqual([['unknown_variable', '/+/1/var']]);
    });
});

describe('formatExpressionValue', () => {
    it('prints plain decimals and joined lists', () => {
        expect(formatExpressionValue(1e-7)).toBe('0.0000001');
        expect(formatExpressionValue(1e14)).toBe('100000000000000');
        expect(formatExpressionValue(true)).toBe('true');
        expect(formatExpressionValue(null)).toBe('');
        expect(formatExpressionValue(['a', null, 2])).toBe('a, 2');
    });
});
