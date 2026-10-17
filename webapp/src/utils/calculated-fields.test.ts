import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison } from '@app/models/types/form-builder-shared';
import { resolvePipeValue } from '@app/utils/answer-piping';
import {
    calculatedAnswer,
    calculationProblems,
    calculationVariables,
    computeCalculatedValues,
    evaluationOrder,
    formatCalculatedValue,
    formulaText,
    getCalculatedFields,
    localToday,
    parseFormulaText,
    pipedInto,
    pruneOrphanedCalculationRefs,
    unansweredAsZero,
    usesAnyAnswer,
    withCalculatedAnswers
} from '@app/utils/calculated-fields';
import { isFieldHiddenByLogic, resolveJump, resolveJumpTargetId } from '@app/utils/conditional-logic';
import { endingToShow } from '@app/utils/endings';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';
import { buildResponsesExport } from '@app/utils/response-export';

const V = (key: string) => ({ var: key });

const field = (id: string, type: string, title: string, properties: any = {}): StandardFormFieldDto => ({ id, index: 0, type, title, properties: { fields: [], ...properties } });
const calc = (id: string, title: string, expression: any, properties: any = {}) => field(id, FieldTypes.CALCULATED, title, { expression, ...properties });
const page = (id: string, fields: StandardFormFieldDto[], properties: any = {}): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields, ...properties } });
const num = (n: number) => ({ type: 'number', number: n });

const QTY = field('qty', FieldTypes.NUMBER, 'Quantity');
const PRICE = field('price', FieldTypes.NUMBER, 'Price');
const ITEMS = field('items', FieldTypes.GROUP, 'Items', { repeat: { minItems: 0, maxItems: 5 }, fields: [field('amount', FieldTypes.NUMBER, 'Amount')] });
const SUBTOTAL = calc('subtotal', 'Subtotal', { '*': [V('qty'), V('price')] });
const TOTAL = calc('total', 'Total', { round: [{ '*': [V('subtotal'), 1.21] }, 2] }, { format: { style: 'currency', decimals: 2, currency: 'EUR' } });

describe('live recompute', () => {
    const slides = [page('p1', [TOTAL]), page('p2', [QTY, PRICE, SUBTOTAL])];

    it('follows dependencies whatever the order on the pages', () => {
        expect(evaluationOrder(getCalculatedFields(slides)).map((f) => f.id)).toEqual(['subtotal', 'total']);
        expect(computeCalculatedValues(slides, { qty: num(3), price: num(19.99) })).toEqual({ subtotal: 59.97, total: 72.56 });
    });

    it('writes the values into the answers and settles', () => {
        const answers = { qty: num(2), price: num(5) };
        const next = withCalculatedAnswers(slides, answers);
        expect(next.subtotal).toEqual({ type: 'number', number: 10 });
        expect(next.total).toEqual({ type: 'number', number: 12.1 });
        // a second pass changes nothing: the same object comes back
        expect(withCalculatedAnswers(slides, next)).toBe(next);
        // an answer changes: the values follow, and an empty result is removed
        const changed = withCalculatedAnswers(slides, { ...next, qty: num(3) });
        expect(changed.subtotal.number).toBe(15);
        // unanswered counts as 0 by default
        const cleared = withCalculatedAnswers(slides, { ...next, qty: undefined });
        expect(cleared.subtotal).toEqual({ type: 'number', number: 0 });
        // switched off, the result goes empty and its answer is removed
        const strict = [page('p', [QTY, PRICE, calc('subtotal', 'Subtotal', { '*': [V('qty'), V('price')] }, { unansweredAsZero: false })])];
        const strictNext = withCalculatedAnswers(strict, answers);
        expect(withCalculatedAnswers(strict, { ...strictNext, qty: undefined }).subtotal).toBeUndefined();
    });

    it('reads group lists, hidden fields and today', () => {
        const form = [page('p', [ITEMS, calc('sum', 'Sum', { sum: [V('items.amount')] }), calc('src', 'Source', { concat: [V('utm'), '-', { today: [] }] })])];
        const values = computeCalculatedValues(form, { items: { type: 'group', items: [{ amount: num(2) }, {}, { amount: num(0.5) }] } }, { utm: 'mail' }, '2026-10-17');
        expect(values).toEqual({ sum: 2.5, src: 'mail-2026-10-17' });
    });

    it('stores booleans and texts in their own slots', () => {
        expect(calculatedAnswer(true)).toEqual({ type: 'boolean', boolean: true });
        expect(calculatedAnswer('adult')).toEqual({ type: 'text', text: 'adult' });
        expect(calculatedAnswer(null)).toBeUndefined();
    });

    it('gives the local date', () => {
        expect(localToday(new Date(2026, 0, 5))).toBe('2026-01-05');
    });
});

// Shared with the server (backend tests/app/services/test_calculated_fields.py).
const SHARED = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/calculated-fields.cases.json'), 'utf8')).cases as Array<{
    name: string;
    fields: StandardFormFieldDto[];
    answers: Record<string, any>;
    hidden?: Record<string, string>;
    expected: Record<string, unknown>;
}>;

describe('shared cases', () => {
    it.each(SHARED.map((c) => [c.name, c]))('%s', (_name, c) => {
        expect(computeCalculatedValues([page('p', c.fields)], c.answers, c.hidden ?? {})).toEqual(c.expected);
    });
});

describe('unanswered as 0', () => {
    it('defaults on, off for text, and follows the setting', () => {
        expect(unansweredAsZero(calc('a', 'A', 1))).toBe(true);
        expect(unansweredAsZero(calc('a', 'A', 1, { format: { style: 'percent' } }))).toBe(true);
        expect(unansweredAsZero(calc('a', 'A', 1, { format: { style: 'text' } }))).toBe(false);
        expect(unansweredAsZero(calc('a', 'A', 1, { format: { style: 'currency' }, unansweredAsZero: false }))).toBe(false);
    });

    it('shows a value only once an answer it uses is given', () => {
        const score = calc('score', 'Score', { '+': [V('half'), 1] });
        const half = calc('half', 'Half', { '/': [V('qty'), 2] });
        const slides = [page('p', [QTY, half, score, calc('constant', 'C', 3), calc('src', 'Src', { concat: [V('utm')] })])];
        expect(usesAnyAnswer(score, slides, {})).toBe(false);
        expect(usesAnyAnswer(score, slides, { qty: num(4) })).toBe(true);
        expect(usesAnyAnswer(slides[0].properties!.fields![3], slides, {})).toBe(true);
        expect(usesAnyAnswer(slides[0].properties!.fields![4], slides, {}, { utm: 'mail' })).toBe(true);
    });
});

describe('an ending chosen by a calculation', () => {
    it('follows the live value on the respondent page', () => {
        const total = calc('total', 'Total', { '*': [V('qty'), 25] });
        const jump = { operator: 'AND', conditions: [{ fieldId: 'total', fieldType: FieldTypes.CALCULATED, comparison: Comparison.GREATER_THAN_EQUAL, value: 100 }], target: '__SUBMIT__', endingId: 'large' };
        const slides = [page('p0', [QTY, total], { jumps: [jump] }), page('p1', [])];
        const endings = [
            { id: 'thanks', title: 'Thank you' },
            { id: 'large', name: 'Large order', title: 'Large order' }
        ];
        const reached = (answers: Record<string, any>) => endingToShow(endings, resolveJump(slides[0], withCalculatedAnswers(slides, answers))?.endingId || undefined)?.id;
        expect(reached({ qty: num(4) })).toBe('large');
        expect(reached({ qty: num(3) })).toBe('thanks');
        // a stale value in the answers is recomputed before the jump is decided
        expect(reached({ qty: num(1), total: num(1000) })).toBe('thanks');
    });
});

describe('a hidden calculation piped into text respondents see', () => {
    it('is found in titles, descriptions and endings', () => {
        const pipe = {
            type: 'doc',
            content: [
                {
                    type: 'paragraph',
                    content: [
                        { type: 'text', text: 'Score: ' },
                        { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'risk' } }
                    ]
                }
            ]
        };
        const slides = [
            page('p', [
                QTY,
                calc('risk', 'Risk', 1, { hiddenFromRespondents: true }),
                field('note', FieldTypes.SHORT_TEXT, pipe as any),
                { ...field('other', FieldTypes.SHORT_TEXT, 'Other'), description: 'You scored {{field:risk|?}}' },
                field('fine', FieldTypes.SHORT_TEXT, 'No pipe {{field:riskier}}')
            ])
        ];
        expect(pipedInto(slides, 'risk', [{ message: 'Bye {{ field:risk }}' }])).toEqual(['Score:', 'Other', 'the ending']);
        expect(pipedInto(slides, 'qty')).toEqual([]);
    });
});

describe('responses and exports', () => {
    const form = { formId: 'f', title: 'T', builderVersion: 'v2', fields: [page('p', [QTY, TOTAL])] } as any;
    const response = { responseId: 'r', provider: 'self', createdAt: '', updatedAt: '', answers: { qty: num(2), total: { type: 'number', number: 1234.5 } } } as any;

    it('the table formats the stored value, the export keeps the number', () => {
        expect(getAnswerForField(response, TOTAL)).toBe('€1,234.50');
        const { main } = buildResponsesExport(form, [response]);
        expect(main.rows[0][main.headers.indexOf('Total')]).toBe(1234.5);
    });
});

describe('formatting', () => {
    it.each([
        [1234.5, { style: 'currency', decimals: 2 }, 'en', '€1,234.50'],
        [1234.5, { style: 'currency', decimals: 2 }, 'nl', '€ 1.234,50'],
        [0.256, { style: 'percent' }, 'en', '26%'],
        [0.256, { style: 'percent', decimals: 1 }, 'nl', '25,6%'],
        [1234.5678, { style: 'number', decimals: 2 }, 'en', '1,234.57'],
        [1234.5678, { style: 'number', decimals: 2 }, 'nl', '1.234,57'],
        [1234.5678, undefined, 'en', '1,234.5678'],
        [12, { style: 'text' }, 'nl', '12'],
        ['adult', { style: 'number' }, 'en', 'adult'],
        [null, { style: 'currency' }, 'en', '']
    ])('%s as %j in %s', (value, format, language, expected) => {
        expect(formatCalculatedValue(value as any, format as any, language).replace(/ /g, ' ')).toBe(expected);
    });
});

describe('logic, jumps and piping read calculated values', () => {
    const score = calc('score', 'Score', { '*': [V('qty'), 10] }, { format: { style: 'number', decimals: 1 } });
    const vip = field('vip', FieldTypes.SHORT_TEXT, 'VIP code', {
        logic: { action: 'SHOW', conditions: [{ fieldId: 'score', fieldType: FieldTypes.CALCULATED, comparison: Comparison.GREATER_THAN, value: 50 }] }
    });
    const slides = [page('p', [QTY, score, vip], { jumps: [{ conditions: [{ fieldId: 'score', fieldType: FieldTypes.CALCULATED, comparison: Comparison.IS_EQUAL, value: '90' }], target: '__SUBMIT__' }] })];

    it('shows a question and jumps on the computed value', () => {
        const low = withCalculatedAnswers(slides, { qty: num(2) });
        const high = withCalculatedAnswers(slides, { qty: num(9) });
        expect(isFieldHiddenByLogic(vip, low)).toBe(true);
        expect(isFieldHiddenByLogic(vip, high)).toBe(false);
        expect(resolveJumpTargetId(slides[0], high)).toBe('__SUBMIT__');
        expect(resolveJumpTargetId(slides[0], low)).toBeNull();
    });

    it('pipes the value as the field formats it', () => {
        const answers = withCalculatedAnswers(slides, { qty: num(9) });
        expect(resolvePipeValue('field', 'score', { slides, answers, language: 'nl' })).toBe('90,0');
        expect(resolvePipeValue('field', 'score', { slides, answers: {} })).toBeUndefined();
    });
});

describe('formula text', () => {
    const slides = [page('p', [QTY, PRICE, ITEMS, SUBTOTAL])];
    const variables = calculationVariables(slides, ['utm']);

    it('offers answers, group questions, calculations and hidden fields', () => {
        expect(variables.map((v) => [v.key, v.label, v.kind])).toEqual([
            ['qty', 'Quantity', 'field'],
            ['price', 'Price', 'field'],
            ['items.amount', 'Items.Amount', 'group'],
            ['subtotal', 'Subtotal', 'calculated'],
            ['utm', 'utm', 'hidden']
        ]);
    });

    it('prints with labels and parses them back', () => {
        const text = formulaText({ round: [{ '*': [V('qty'), V('price'), 1.21] }, 2] }, variables);
        expect(text).toBe('round({Quantity} * {Price} * 1.21, 2)');
        expect(parseFormulaText(text, variables).expression).toEqual({ round: [{ '*': [V('qty'), V('price'), 1.21] }, 2] });
        expect(parseFormulaText('sum({Items.Amount}) + {utm}', variables).expression).toEqual({ '+': [{ sum: [V('items.amount')] }, V('utm')] });
    });

    it('reports errors with their position', () => {
        const result = parseFormulaText('{Quantity} * {Height}', variables);
        expect(result.error?.message).toMatch(/Height/);
        expect([result.error?.start, result.error?.end]).toEqual([13, 21]);
        expect(parseFormulaText('{Quantity} = 2', variables).error?.message).toMatch(/==/);
        expect(parseFormulaText('  ', variables)).toEqual({ expression: undefined });
    });
});

describe('builder checks', () => {
    it('finds unknown fields and circles', () => {
        const a = calc('a', 'Alpha', { '+': [V('b'), 1] });
        const b = calc('b', 'Beta', { '+': [V('a'), 1] });
        const problems = calculationProblems([page('p', [QTY, a, b, calc('c', 'C', V('ghost'))])]);
        expect(problems.filter((p) => p.fieldId === 'c').map((p) => p.path)).toEqual(['/var']);
        expect(problems.find((p) => p.fieldId === 'a')?.message).toMatch(/circle.*'Alpha' → 'Beta'/);
    });

    it('turns references to deleted questions into null', () => {
        const id = '0b7c5f8e-6a1d-4c3e-9f2a-1b2c3d4e5f60';
        const slides = [page('p', [QTY, calc('c', 'C', { '+': [V('qty'), V(id), V('utm'), V('gone.child')] })])];
        pruneOrphanedCalculationRefs(slides);
        expect(slides[0].properties!.fields![1].properties!.expression).toEqual({ '+': [V('qty'), null, V('utm'), null] });
        pruneOrphanedCalculationRefs(slides, []);
        expect(slides[0].properties!.fields![1].properties!.expression).toEqual({ '+': [V('qty'), null, null, null] });
    });
});
