import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { firstPageWithError, historyBackTo, serverAnswerErrors, serverInvalidations, serverProblemMessage } from './server-answer-errors';

const q = (id: string, type = FieldTypes.SHORT_TEXT, properties: Record<string, any> = {}) => ({ id, index: 0, type, properties }) as StandardFormFieldDto;
const page = (id: string, fields: StandardFormFieldDto[]) => ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;

const SLIDES = [
    page('p1', [q('name'), q('grid', FieldTypes.MATRIX, { fields: [q('row1', FieldTypes.MULTIPLE_CHOICE), q('row2', FieldTypes.MULTIPLE_CHOICE)] })]),
    page('p2', [q('people', FieldTypes.GROUP, { repeat: { minItems: 1, maxItems: 3 }, fields: [q('person')] }), q('age', FieldTypes.NUMBER)])
];

const refused = (errors: unknown) => ({ status: 422, data: { code: 'invalid_answers', message: 'Some answers are missing or not valid.', errors } });

describe('reading a refused submission', () => {
    it('takes the answer problems of a 422 invalid_answers', () => {
        expect(serverAnswerErrors(refused([{ fieldId: 'age', rule: 'too_large' }]))).toEqual([{ fieldId: 'age', rule: 'too_large' }]);
    });

    it('is null for any other failure, so the generic message shows', () => {
        expect(serverAnswerErrors({ status: 500, data: {} })).toBeNull();
        expect(serverAnswerErrors({ status: 422, data: 'Some group text' })).toBeNull();
        expect(serverAnswerErrors({ status: 422, data: { code: 'other', errors: [] } })).toBeNull();
        expect(serverAnswerErrors(undefined)).toBeNull();
        expect(
            serverAnswerErrors(
                refused([
                    { fieldId: 1, rule: 'type' },
                    { fieldId: 'a', rule: 'type', item: -1 }
                ])
            )
        ).toBeNull();
    });
});

describe('putting the problems on the questions', () => {
    it('keys them by the id each question renders under, in its own codes', () => {
        const errors = [
            { fieldId: 'name', rule: 'required' },
            { fieldId: 'age', rule: 'not_integer' },
            { fieldId: 'age', rule: 'type' },
            { fieldId: 'row2', rule: 'choice' },
            { fieldId: 'person', rule: 'too_short', item: 1 },
            { fieldId: 'nope', rule: 'unknown_field' },
            { fieldId: 'name', rule: 'something_new' }
        ];
        expect(serverInvalidations(SLIDES, errors)).toEqual({
            name: ['REQUIRED'],
            age: ['NOT_INTEGER', 'SERVER_TYPE'],
            grid: ['SERVER_CHOICE'],
            'person::1': ['TOO_SHORT']
        });
    });

    it('goes to the first page with a problem the respondent can see', () => {
        expect(
            firstPageWithError(SLIDES, [
                { fieldId: 'age', rule: 'type' },
                { fieldId: 'row1', rule: 'choice' }
            ])
        ).toBe(0);
        expect(firstPageWithError(SLIDES, [{ fieldId: 'person', rule: 'required', item: 0 }])).toBe(1);
        expect(firstPageWithError(SLIDES, [{ fieldId: 'nope', rule: 'unknown_field' }])).toBe(-1);
    });

    it('retraces the path back to that page, as Back would', () => {
        expect(historyBackTo([0, 1, 3], 4, 1)).toEqual([0]);
        expect(historyBackTo([0, 1], 2, 2)).toEqual([0, 1]);
        expect(historyBackTo([0], 1, 3)).toEqual([0, 1]);
    });
});

describe('messages', () => {
    it('server-only problems have messages in English and Dutch', () => {
        const t = (key: string) => key;
        expect(serverProblemMessage('SERVER_TYPE', t)).toBe('RULE.SERVER_TYPE');
        expect(serverProblemMessage('SERVER_CHOICE', t)).toBe('RULE.SERVER_CHOICE');
        for (const language of ['en', 'nl']) {
            const respondent = JSON.parse(readFileSync(resolve(__dirname, `../../public/locales/${language}/respondent.json`), 'utf-8'));
            expect(respondent.RULE.SERVER_TYPE).toBeTruthy();
            expect(respondent.RULE.SERVER_CHOICE).toBeTruthy();
            expect(respondent.NAV.SUBMIT_INVALID).toBeTruthy();
        }
    });
});
