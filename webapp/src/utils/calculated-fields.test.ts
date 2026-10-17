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
    pruneOrphanedCalculationRefs,
    withCalculatedAnswers
} from '@app/utils/calculated-fields';
import { isFieldHiddenByLogic, resolveJumpTargetId } from '@app/utils/conditional-logic';

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
        const cleared = withCalculatedAnswers(slides, { ...next, qty: undefined });
        expect(cleared.subtotal).toBeUndefined();
        expect(cleared.total).toBeUndefined();
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
