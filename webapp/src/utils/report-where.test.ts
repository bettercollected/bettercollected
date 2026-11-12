import i18n from 'i18next';
import { afterEach, describe, expect, it } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { catalogue } from '@app/test/report-fixtures';
import { ReportClause, fieldOf } from '@app/utils/report';
import { blankClause, clauseProblem, describeClause, filterableFields, withOp } from '@app/utils/report-where';

const t = (key: string, options?: Record<string, unknown>) => i18n.t(key, options) as string;
const clause = (changes: Partial<ReportClause>): ReportClause => ({ field: 'q:team', op: 'is', value: 'north', ...changes });

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('whether a condition can be asked for', () => {
    const problem = (changes: Partial<ReportClause>) => clauseProblem(clause(changes), catalogue);

    it('accepts a condition that suits its question', () => {
        for (const ok of [
            clause({}),
            clause({ op: 'any_of', value: ['north', 'south'] }),
            clause({ field: 'q:tools', op: 'has_all', value: ['mail', 'chat'] }),
            clause({ field: 'q:score', op: 'between', value: [1, 3] }),
            clause({ field: 'q:score', op: '>=', value: 4.5 }),
            clause({ field: 'q:remote', op: 'is', value: false }),
            { field: 'q:years', op: 'is_empty' },
            { field: 'q:team', op: 'is_not_empty' }
        ]) expect(clauseProblem(ok, catalogue)).toBeUndefined();
    });

    it('names a question the form no longer has', () => {
        expect(problem({ field: 'q:gone' })).toBe('unknown');
    });

    it.each([
        ['an operator the kind does not take', { op: '>' }],
        ['a value that is not an option', { value: 'ghost' }],
        ['a list where one option is needed', { value: ['north'] }],
        ['one option where a list is needed', { op: 'any_of', value: 'north' }],
        ['an empty list', { op: 'any_of', value: [] }],
        ['no value', { value: undefined }],
        ['a value for is_empty', { op: 'is_empty', value: 'north' }],
        ['text for a number', { field: 'q:score', op: '>', value: '3' }],
        ['a number out of range', { field: 'q:score', op: '>', value: 10 ** 16 }],
        ['a between with one end', { field: 'q:score', op: 'between', value: [1] }],
        ['a between the wrong way round', { field: 'q:score', op: 'between', value: [5, 1] }],
        ['a yes/no that is a string', { field: 'q:remote', op: 'is', value: 'yes' }]
    ])('refuses %s', (_name, changes) => {
        expect(problem(changes as Partial<ReportClause>)).toBe('invalid');
    });
});

describe('building a condition', () => {
    it('lists the questions that take conditions', () => {
        expect(filterableFields(catalogue).map((f) => f.key)).toEqual(['q:team', 'q:tools', 'q:score', 'q:years', 'q:remote']);
        expect(filterableFields({ ...catalogue, fields: catalogue.fields.map((f) => ({ ...f, filterOps: undefined })) })).toEqual([]);
    });

    it('starts from the first operator and an option, and resets the value with the operator', () => {
        const team = fieldOf(catalogue, 'q:team')!;
        expect(blankClause(team)).toEqual({ field: 'q:team', op: 'is', value: 'north' });
        expect(withOp(blankClause(team), team, 'any_of')).toEqual({ field: 'q:team', op: 'any_of', value: ['north'] });
        expect(withOp(blankClause(team), team, 'is_empty')).toEqual({ field: 'q:team', op: 'is_empty' });
        const score = fieldOf(catalogue, 'q:score')!;
        expect(withOp(blankClause(score), score, 'between')).toEqual({ field: 'q:score', op: 'between', value: [0, 0] });
        for (const field of catalogue.fields) expect(blankClause(field).field).toBe(field.key);
    });
});

describe('a condition as a sentence', () => {
    const say = (value: ReportClause, locale = 'en') => describeClause(value, catalogue, t, locale);

    it('names the question, the operator and the options by their labels', () => {
        expect(say(clause({}))).toBe('Which team are you in? is North');
        expect(say(clause({ op: 'any_of', value: ['north', 'south'] }))).toBe('Which team are you in? is one of North, South');
        expect(say({ field: 'q:tools', op: 'has_all', value: ['mail', 'chat'] })).toBe('Which tools do you use? includes all of Mail, Chat');
        expect(say({ field: 'q:score', op: 'between', value: [2, 4] })).toBe('How satisfied are you? is between 2 – 4');
        expect(say({ field: 'q:remote', op: 'is', value: true })).toBe('Do you work remotely? is Yes');
        expect(say({ field: 'q:years', op: 'is_empty' })).toBe('Years at the organisation has no answer');
    });

    it('formats numbers in the locale and says it in Dutch', async () => {
        expect(say({ field: 'q:years', op: '>', value: 1234.5 })).toBe('Years at the organisation is more than 1,234.5');
        await i18n.changeLanguage('nl');
        expect(say({ field: 'q:years', op: '>', value: 1234.5 }, 'nl')).toBe('Years at the organisation is meer dan 1.234,5');
        expect(say({ field: 'q:remote', op: 'is', value: false }, 'nl')).toBe('Do you work remotely? is Nee');
        expect(say({ field: 'q:years', op: 'is_not_empty' }, 'nl')).toBe('Years at the organisation heeft een antwoord');
    });

    it('does not print an id it has no label for', () => {
        expect(say(clause({ value: 'ghost' }))).toContain('ghost');
        expect(say(clause({ field: 'q:gone', op: 'is_empty' }))).toBe('q:gone has no answer');
    });
});
