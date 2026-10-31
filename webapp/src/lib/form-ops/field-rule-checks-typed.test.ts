import { describe, expect, it } from 'vitest';

import { fieldRuleProblems } from './field-rule-checks';
import type { FormDoc } from './types';

/** A page with one question of `type` that carries `rule`. */
const formWith = (type: string, rule: Record<string, unknown>, extra: Record<string, unknown> = {}): FormDoc =>
    ({
        title: 'Typed rules',
        builderVersion: 'v2',
        fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields: [{ id: 'q', index: 0, type, title: 'Question', properties: { rules: [{ id: 'r1', when: { expression: true }, ...rule }], ...extra } }] } }]
    }) as unknown as FormDoc;

describe('rules on time, day and currency questions (the same as the backend)', () => {
    it.each(['time', 'day', 'currency'])('may lock the value of a %s question', (type) => {
        expect(fieldRuleProblems(formWith(type, { then: { readOnly: true } }))).toEqual([]);
    });

    it.each([
        ['time', '09:30', '13:61'],
        ['day', '2026-11-05', '2026-02-30'],
        ['currency', '12.50', 'twelve']
    ])('may set a %s question to a value that fits it and refuses one that does not', (type, good, bad) => {
        expect(fieldRuleProblems(formWith(type, { then: { setValue: { const: good } } }))).toEqual([]);
        const problems = fieldRuleProblems(formWith(type, { then: { setValue: { const: bad } } }));
        expect(problems).toHaveLength(1);
        expect(problems[0].message).toContain('sets a value that does not fit it');
    });

    it('says what a time, a day and an amount look like', () => {
        const what = (type: string) => fieldRuleProblems(formWith(type, { then: { setValue: { const: '??' } } }))[0].message;
        expect(what('time')).toContain('a time written as HH:MM (24-hour)');
        expect(what('day')).toContain('a date written as YYYY-MM-DD');
        expect(what('currency')).toContain("an amount such as 12.50 (in the question's first currency)");
    });

    it('still refuses to lock a type that holds no value to set', () => {
        const [problem] = fieldRuleProblems(formWith('email', { then: { readOnly: true } }));
        expect(problem.message).toContain('short and long text, number, date, day, time, currency, yes/no and single-choice questions');
    });
});
