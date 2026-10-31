import { describe, expect, it } from 'vitest';

import { RULE_COST_PER_RESPONSE, formHasFieldRules, isCalendarDate, resolveFieldRules, withDerivedAnswers } from '@app/lib/field-rules';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { validateAnswerRulesInSlide } from '@app/utils/answer-rules';
import { validateDateRulesInSlide } from '@app/utils/date-rules';
import { validateGroupsInSlide } from '@app/utils/repeating-groups';

const text = (value: string) => ({ type: 'text', text: value });
const num = (value: number) => ({ type: 'number', number: value });
const is = (fieldId: string, value: string) => ({ conditions: [{ fieldId, fieldType: 'short_text', comparison: 'IS_EQUAL', value }] });
const question = (id: string, type: string, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: id, ...extra });
const page = (fields: StandardFormFieldDto[]) => [{ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }] as StandardFormFieldDto[];
const ruled = (id: string, type: string, rules: unknown[], extra: Partial<StandardFormFieldDto> = {}) => question(id, type, { ...extra, properties: { ...extra.properties, rules: rules as any } });

describe('resolveFieldRules', () => {
    it('is a no-op for a form without rules or calculations: the same answers object, no states', () => {
        const slides = page([question('a', FieldTypes.SHORT_TEXT), question('b', FieldTypes.NUMBER)]);
        const answers = { a: text('x') };
        const resolved = resolveFieldRules(slides, answers);
        expect(resolved.answers).toBe(answers);
        expect(resolved.states.isEmpty).toBe(true);
        expect(resolved.derivedIds.size).toBe(0);
        expect(formHasFieldRules(slides)).toBe(false);
        expect(withDerivedAnswers(slides, answers).answers).toBe(answers);
    });

    it('never changes the answers it is given', () => {
        const slides = page([question('a', FieldTypes.SHORT_TEXT), ruled('n', FieldTypes.NUMBER, [{ id: 'r', when: is('a', 'x'), then: { setValue: { const: 4 } } }])]);
        const answers = { a: text('x'), n: num(1) };
        const copy = JSON.parse(JSON.stringify(answers));
        const resolved = resolveFieldRules(slides, answers);
        expect(answers).toEqual(copy);
        expect(resolved.answers.n).toEqual(num(4));
    });

    it('settles: deriving from derived answers changes nothing', () => {
        const slides = page([question('a', FieldTypes.SHORT_TEXT), ruled('n', FieldTypes.NUMBER, [{ id: 'r', when: is('a', 'x'), then: { setValue: { const: 4 } } }])]);
        const first = withDerivedAnswers(slides, { a: text('x') }).answers;
        expect(first.n).toEqual(num(4));
        expect(withDerivedAnswers(slides, first).answers).toBe(first);
    });

    it('drops a locked question\'s own answer, and marks it for the page ("valued" only when a value was set)', () => {
        const slides = page([
            question('a', FieldTypes.SHORT_TEXT),
            ruled('plain', FieldTypes.SHORT_TEXT, [{ id: 'r1', when: is('a', 'x'), then: { readOnly: true } }]),
            ruled('set', FieldTypes.NUMBER, [{ id: 'r2', when: is('a', 'x'), then: { setValue: { const: 2 } } }])
        ]);
        const { answers, states } = resolveFieldRules(slides, { a: text('x'), plain: text('mine') });
        expect(answers.plain).toBeUndefined();
        expect([...states.locked].sort()).toEqual(['plain', 'set']);
        expect([...states.valued]).toEqual(['set']);
        expect(states.isRequired('plain', true)).toBe(false);
    });

    it('stops applying rules when a response is over the evaluation budget, as the server refuses it', () => {
        const heavy = { max: Array.from({ length: 200 }, () => ({ var: 'g.c' })) };
        const group = question('g', FieldTypes.GROUP, { properties: { repeat: { minItems: 1, maxItems: 50 }, fields: [question('c', FieldTypes.NUMBER)] } });
        const rule = (id: string) => ({ id, when: { expression: { '>': [heavy, 0] } }, then: { description: 'd' } });
        const fields = ['b1', 'b2', 'b3'].map((id) =>
            ruled(
                id,
                FieldTypes.SHORT_TEXT,
                Array.from({ length: 8 }, (_, i) => rule(`${id}-${i}`))
            )
        );
        const resolved = resolveFieldRules(page([group, ...fields]), { g: { type: 'group', items: [{ c: num(1) }] } });
        expect(RULE_COST_PER_RESPONSE).toBe(200_000);
        expect(resolved.tooCostly).toBe(true);
        expect(resolved.states.isEmpty).toBe(true);
        // one rule is far below it
        expect(resolveFieldRules(page([group, ...fields.slice(0, 1).map((f) => ({ ...f, properties: { rules: [(f.properties!.rules as any)[0]] } }))]), { g: { type: 'group', items: [{ c: num(1) }] } }).tooCostly).toBeUndefined();
    });

    it('reads at most 8 rules per question', () => {
        const rules = Array.from({ length: 9 }, (_, i) => ({ id: `r${i}`, when: is('a', 'x'), then: i === 8 ? { required: true } : { description: `d${i}` } }));
        const resolved = resolveFieldRules(page([question('a', FieldTypes.SHORT_TEXT), ruled('b', FieldTypes.SHORT_TEXT, rules)]), { a: text('x') });
        expect(resolved.states.isRequired('b', false)).toBe(false);
        expect(resolved.states.text('b')?.description).toBe('d7');
    });

    it('ignores rules that are not objects, and unknown effect keys', () => {
        const slides = page([question('a', FieldTypes.SHORT_TEXT), ruled('b', FieldTypes.SHORT_TEXT, [null, 'x', { id: 'r', when: is('a', 'x'), then: { bogus: true } }])]);
        expect(() => resolveFieldRules(slides, { a: text('x') })).not.toThrow();
        expect(resolveFieldRules(slides, { a: text('x') }).states.isEmpty).toBe(true);
    });
});

describe('isCalendarDate', () => {
    it.each([
        ['2026-03-01', true],
        ['2024-02-29', true],
        ['0050-01-01', true],
        ['2026-02-29', false],
        ['2026-3-1', false],
        ['0000-01-01', false],
        ['2026-13-01', false],
        [20260301, false]
    ])('%s', (value, expected) => expect(isCalendarDate(value)).toBe(expected));
});

describe('what a locked question is not held to', () => {
    const locked = new Set(['d']);
    const dateQuestion = question('d', FieldTypes.DATE, { properties: { dateRules: [{ comparison: 'after', target: 'date', date: '2030-01-01' }] as any } });
    const answers = { d: { type: 'date', date: '2020-01-01' } };

    it('has no date rules to meet', () => {
        expect(Object.keys(validateDateRulesInSlide([dateQuestion], answers, { d: dateQuestion }, '2026-03-15'))).toEqual(['d']);
        expect(validateDateRulesInSlide([dateQuestion], answers, { d: dateQuestion }, '2026-03-15', locked)).toEqual({});
    });

    it('has no answer rules to meet', () => {
        const short = question('d', FieldTypes.SHORT_TEXT, { validations: { minLength: 5 } });
        expect(Object.keys(validateAnswerRulesInSlide([short], { d: text('ab') }))).toEqual(['d']);
        expect(validateAnswerRulesInSlide([short], { d: text('ab') }, undefined, locked)).toEqual({});
    });
});

describe('Required inside a repeating group follows the rules per item', () => {
    it('requires the question only in the items whose rule holds', () => {
        const group = question('g', FieldTypes.GROUP, {
            properties: { repeat: { minItems: 1, maxItems: 3 }, fields: [question('c1', FieldTypes.SHORT_TEXT), ruled('c2', FieldTypes.SHORT_TEXT, [{ id: 'r', when: is('c1', 'x'), then: { required: true } }])] }
        });
        const slides = page([group]);
        const answers = { g: { type: 'group', items: [{ c1: text('x') }, { c1: text('y') }] } };
        const { states } = resolveFieldRules(slides, answers);
        expect(validateGroupsInSlide([group], answers, undefined, states)).toEqual({ 'c2::0': ['REQUIRED'] });
        // without the states the static flag decides
        expect(validateGroupsInSlide([group], answers)).toEqual({});
    });
});
