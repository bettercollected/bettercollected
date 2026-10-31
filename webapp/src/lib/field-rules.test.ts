import { describe, expect, it } from 'vitest';

import { RULE_COST_PER_RESPONSE, formHasFieldRules, isCalendarDate, resolveFieldRules, withDerivedAnswers } from '@app/lib/field-rules';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { validateAnswerRulesInSlide } from '@app/utils/answer-rules';
import { evaluateConditions } from '@app/utils/conditional-logic';
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

describe('the text a condition reads is capped', () => {
    const when = (comparison: string) => ({ conditions: [{ fieldId: 'a', fieldType: 'long_text', comparison, value: 'x' }] });
    const slides = (comparison: string) => page([question('a', FieldTypes.LONG_TEXT), ruled('b', FieldTypes.SHORT_TEXT, [{ id: 'r', when: when(comparison), then: { required: true } }])]);
    const active = (comparison: string, answer: string) => resolveFieldRules(slides(comparison), { a: text(answer) }).states.isRequired('b', false);

    it.each([
        [10_000, 'IS_NOT_EMPTY', true],
        [10_001, 'IS_NOT_EMPTY', false],
        [10_000, 'IS_EMPTY', false],
        [10_001, 'IS_EMPTY', true],
        [10_000, 'CONTAINS', true],
        [10_001, 'CONTAINS', false],
        // far over: decided without counting its code points
        [1_000_000, 'IS_NOT_EMPTY', false]
    ])('%s characters, %s: active %s', (length, comparison, expected) => {
        expect(active(comparison, 'x'.repeat(length))).toBe(expected);
    });

    it('counts code points, not UTF-16 units (as the server does)', () => {
        // 12,000 units but 6,000 code points: under the cap
        expect(active('IS_NOT_EMPTY', '\u{1F600}'.repeat(6000))).toBe(true);
        // 10,001 code points: over it
        expect(active('IS_NOT_EMPTY', '\u{1F600}'.repeat(10_001))).toBe(false);
    });

    it('reads the options of a choice question the same way', () => {
        const choice = question('c', FieldTypes.DROP_DOWN, { properties: { choices: [{ id: 'nl', value: 'Netherlands' }] } });
        const slidesWithChoice = page([choice, ruled('b', FieldTypes.SHORT_TEXT, [{ id: 'r', when: { conditions: [{ fieldId: 'c', fieldType: 'dropdown', comparison: 'CONTAINS', value: 'x' }] }, then: { required: true } }])]);
        const other = (length: number) => ({ c: { type: 'choice', choice: { other: 'x'.repeat(length) } } });
        expect(resolveFieldRules(slidesWithChoice, other(10_000)).states.isRequired('b', false)).toBe(true);
        expect(resolveFieldRules(slidesWithChoice, other(10_001)).states.isRequired('b', false)).toBe(false);
    });

    it('is for field rules only: conditional logic reads the whole answer', () => {
        const conditions = [{ fieldId: 'a', fieldType: 'long_text', comparison: 'IS_NOT_EMPTY' }] as any;
        const answers = { a: text('x'.repeat(20_000)) };
        expect(evaluateConditions('AND' as any, conditions, answers)).toBe(true);
        expect(evaluateConditions('AND' as any, conditions, answers, undefined, 10_000)).toBe(false);
    });
});

describe('a condition on an internal question is not active', () => {
    it('as the browser is not served the question and the server drops its answer', () => {
        const slides = page([
            question('a', FieldTypes.SHORT_TEXT, { internal: true }),
            ruled('b', FieldTypes.SHORT_TEXT, [
                { id: 'r1', when: { conditions: [{ fieldId: 'a', fieldType: 'short_text', comparison: 'IS_EMPTY' }] }, then: { required: true } },
                { id: 'r2', when: is('a', 'x'), then: { title: 'seen' } }
            ])
        ]);
        expect(resolveFieldRules(slides, { a: text('x') }).states.isEmpty).toBe(true);
    });
});

describe('values that read each other in a circle', () => {
    const circle = (type: FieldTypes, read: (id: string) => unknown) =>
        page([
            question('a', FieldTypes.SHORT_TEXT),
            ruled('t1', type, [{ id: 'r1', when: is('a', 'x'), then: { setValue: { expression: read('t2') } } }]),
            ruled('t2', type, [{ id: 'r2', when: is('a', 'x'), then: { setValue: { expression: read('t1') } } }])
        ]);

    it('have no value, so the page settles (it used to swap them for ever)', () => {
        const slides = circle(FieldTypes.SHORT_TEXT, (id) => ({ var: id }));
        const first = withDerivedAnswers(slides, { a: text('x'), t1: text('p'), t2: text('q') }).answers;
        expect(first.t1).toBeUndefined();
        expect(first.t2).toBeUndefined();
        expect(first.a).toEqual(text('x'));
        expect(withDerivedAnswers(slides, first).answers).toBe(first);
        // locked all the same: the form owns them
        expect([...resolveFieldRules(slides, first).states.locked].sort()).toEqual(['t1', 't2']);
    });

    it('and a question that reads one of them has none either', () => {
        const slides = page([
            question('a', FieldTypes.SHORT_TEXT),
            ruled('t1', FieldTypes.SHORT_TEXT, [{ id: 'r1', when: is('a', 'x'), then: { setValue: { expression: { var: 't2' } } } }]),
            ruled('t2', FieldTypes.SHORT_TEXT, [{ id: 'r2', when: is('a', 'x'), then: { setValue: { expression: { var: 't1' } } } }]),
            ruled('t3', FieldTypes.SHORT_TEXT, [{ id: 'r3', when: is('a', 'x'), then: { setValue: { expression: { var: 't1' } } } }])
        ]);
        const { answers } = resolveFieldRules(slides, { a: text('x'), t3: text('mine') });
        expect(answers.t3).toBeUndefined();
    });
});

describe('questions are keyed by id, whatever the id', () => {
    it('stores the answer of a question called __proto__', () => {
        const slides = page([question('a', FieldTypes.SHORT_TEXT), ruled('__proto__', FieldTypes.NUMBER, [{ id: 'r', when: is('a', 'x'), then: { setValue: { const: 4 } } }])]);
        const { answers, states } = resolveFieldRules(slides, { a: text('x') });
        expect(Object.keys(answers).sort()).toEqual(['__proto__', 'a']);
        expect(Object.getOwnPropertyDescriptor(answers, '__proto__')?.value).toEqual(num(4));
        expect(states.locked.has('__proto__')).toBe(true);
        expect(Object.getPrototypeOf(answers)).toBeNull();
        // and a rule can read it
        const reader = page([
            ruled('__proto__', FieldTypes.NUMBER, [{ id: 'r', when: is('a', 'x'), then: { setValue: { const: 4 } } }]),
            question('a', FieldTypes.SHORT_TEXT),
            ruled('b', FieldTypes.SHORT_TEXT, [{ id: 'rb', when: { expression: { '==': [{ var: '__proto__' }, 4] } }, then: { required: true } }])
        ]);
        expect(resolveFieldRules(reader, { a: text('x') }).states.isRequired('b', false)).toBe(true);
        // a condition reads the answer it set (the answers a rule reads are keyed the same way)
        const textual = page([
            question('a', FieldTypes.SHORT_TEXT),
            ruled('__proto__', FieldTypes.SHORT_TEXT, [{ id: 'r', when: is('a', 'x'), then: { setValue: { const: 'set' } } }]),
            ruled('b', FieldTypes.SHORT_TEXT, [{ id: 'rb', when: is('__proto__', 'set'), then: { required: true } }])
        ]);
        expect(resolveFieldRules(textual, { a: text('x') }).states.isRequired('b', false)).toBe(true);
    });
});

describe('the cost of a very wide expression', () => {
    it('is counted, not thrown at (a spread of a long list overflows the stack)', () => {
        const wide = { '+': Array.from({ length: 1_500_000 }, () => 1) };
        const slides = page([ruled('b', FieldTypes.SHORT_TEXT, [{ id: 'r', when: { expression: { '>': [wide, 0] } }, then: { required: true } }])]);
        let resolved: ReturnType<typeof resolveFieldRules> | undefined;
        expect(() => (resolved = resolveFieldRules(slides, {}))).not.toThrow();
        // over the budget: no rule applied, as the server refuses such a response
        expect(resolved?.tooCostly).toBe(true);
    });
});
