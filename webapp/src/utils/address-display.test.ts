import { describe, expect, it } from 'vitest';

import { Comparison } from '@app/models/types/form-builder-shared';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { comparisonsForField } from '@app/views/molecules/form-builder/condition-editor-shared';

import { resolvePipeValue } from './answer-piping';
import { answerRuleMessage, answerRuleKind, checkAnswerRules } from './answer-rules';
import { calculationVariables } from './calculated-fields';
import { evaluateConditions, getComparableAnswerValue } from './conditional-logic';
import { getAnswerDisplayText, getAnswerForField } from './form-builder-block-utils';
import { answerLines } from './review-page';
import { isServerProblem } from './server-answer-errors';

const field: StandardFormFieldDto = { id: 'home', index: 0, type: FieldTypes.ADDRESS, title: 'Home' };
const answer = (address: Record<string, string>) => ({ type: 'address', address });
const FULL = { street: 'Keizersgracht', house_number: '12', house_number_addition: 'A', postcode: '1015 CS', city: 'Amsterdam', country: 'NL' };

describe('an address in a table, an export and a page of answers', () => {
    it('is one line in the same words as the server and the CSV', () => {
        const response = { answers: { home: answer(FULL) } } as any;
        expect(getAnswerForField(response, field)).toBe('Keizersgracht 12 A, 1015 CS Amsterdam');
        expect(getAnswerDisplayText(response, field)).toBe('Keizersgracht 12 A, 1015 CS Amsterdam');
        expect(getAnswerForField({ answers: { home: answer({ ...FULL, country: 'BE' }) } } as any, field)).toBe('Keizersgracht 12 A, 1015 CS Amsterdam, BE');
        expect(getAnswerForField({ answers: {} } as any, field)).toBe('');
    });

    it('is a line per line of the address on the review page', () => {
        const t = (key: string) => key;
        expect(answerLines(field, { home: answer(FULL) }, 'en', t)).toEqual(['Keizersgracht 12 A', '1015 CS Amsterdam']);
        expect(answerLines(field, { home: answer({ ...FULL, country: 'BE' }) }, 'nl', t)).toEqual(['Keizersgracht 12 A', '1015 CS Amsterdam', 'België']);
        expect(answerLines(field, {}, 'en', t)).toEqual([]);
    });

    it('is never piped into a title', () => {
        const slides = [{ id: 's', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field] } }] as any;
        expect(resolvePipeValue('field', 'home', { slides, answers: { home: answer(FULL) }, hiddenValues: {}, language: 'en' } as any)).toBeUndefined();
    });
});

describe('an address in logic', () => {
    const condition = (comparison: string, value?: string) => ({ fieldId: 'home', fieldType: FieldTypes.ADDRESS, comparison, value }) as any;
    const holds = (comparison: string, value: string | undefined, address: Record<string, string> | null = FULL) => evaluateConditions('AND', [condition(comparison, value)], address ? { home: answer(address) } : {});

    it('reads the postcode as text', () => {
        expect(getComparableAnswerValue(answer(FULL), FieldTypes.ADDRESS)).toBe('1015 CS');
        expect(getComparableAnswerValue(answer({ street: 'A' }), FieldTypes.ADDRESS)).toBeUndefined();
        expect(getComparableAnswerValue({ address: 'x' }, FieldTypes.ADDRESS)).toBeUndefined();
    });

    it('asks the five questions an address has', () => {
        expect(holds(Comparison.STARTS_WITH, '10')).toBe(true);
        expect(holds(Comparison.STARTS_WITH, '1015 c')).toBe(true);
        expect(holds(Comparison.STARTS_WITH, '20')).toBe(false);
        expect(holds(Comparison.IS_EQUAL, '1015 CS')).toBe(true);
        expect(holds(Comparison.IS_NOT_EQUAL, '1015 CT')).toBe(true);
        expect(holds(Comparison.IS_NOT_EMPTY, undefined)).toBe(true);
        expect(holds(Comparison.IS_EMPTY, undefined, null)).toBe(true);
        expect(holds(Comparison.IS_NOT_EMPTY, undefined, null)).toBe(false);
    });

    it('never lets another comparison hold', () => {
        for (const comparison of [Comparison.CONTAINS, Comparison.GREATER_THAN, Comparison.ENDS_WITH, Comparison.DOES_NOT_CONTAIN]) expect(holds(comparison, '10')).toBe(false);
    });

    it('offers the builder those five and no others', () => {
        expect(comparisonsForField(field)).toEqual([Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL, Comparison.STARTS_WITH, Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY]);
    });
});

describe('the answer rules of an address', () => {
    const t = (key: string, options?: Record<string, unknown>) => `${key}${options ? JSON.stringify(options) : ''}`;

    it('is a kind of its own, and checks what the server checks', () => {
        expect(answerRuleKind(field)).toBe('address');
        expect(checkAnswerRules(field, answer(FULL))).toEqual([]);
        expect(checkAnswerRules(field, answer({ ...FULL, postcode: '1015 SS' }))).toEqual(['FORMAT']);
        expect(checkAnswerRules(field, answer({ ...FULL, street: '' }))).toEqual(['REQUIRED']);
        expect(checkAnswerRules(field, answer({ ...FULL, country: 'DE', postcode: '10115' }))).toEqual(['COUNTRY']);
        expect(checkAnswerRules(field, answer({ ...FULL, street: 'x'.repeat(101) }))).toEqual(['TOO_LONG']);
        expect(checkAnswerRules(field, {})).toEqual([]);
        expect(checkAnswerRules({ ...field, properties: { countries: ['NL', 'DE'] } }, answer({ ...FULL, country: 'DE', postcode: '10115' }))).toEqual([]);
    });

    it('says what is wrong in the respondent\'s words', () => {
        expect(answerRuleMessage(field, 'REQUIRED', t)).toBe('RULE.ADDRESS_INCOMPLETE');
        expect(answerRuleMessage(field, 'FORMAT', t)).toBe('RULE.FORMAT_ADDRESS');
        expect(answerRuleMessage(field, 'TOO_LONG', t)).toBe('RULE.ADDRESS_TOO_LONG');
        expect(answerRuleMessage({ ...field, properties: { countries: ['NL', 'BE'] } }, 'COUNTRY', t, 'en')).toBe('RULE.COUNTRY{"countries":"Netherlands, Belgium"}');
    });

    it('reads the server\'s country problem as the browser\'s', () => {
        expect(isServerProblem('country')).toBe(false);
    });
});

describe('an address in formulas', () => {
    it('is no variable', () => {
        const other: StandardFormFieldDto = { id: 'age', index: 1, type: FieldTypes.NUMBER, title: 'Age' };
        const slides = [{ id: 's', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field, other] } }] as any;
        expect(calculationVariables(slides).map((variable) => variable.key)).toEqual(['age']);
    });
});
