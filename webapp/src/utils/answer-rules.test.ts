import { readFileSync } from 'fs';
import { resolve } from 'path';

import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import { FORMAT_PRESETS, INTEGER_PATTERN, PATTERN_MAX_LENGTH, answerRuleConflicts, answerRuleKind, answerRuleMessage, checkAnswerRules, compilePattern, presetForPattern, summarizeAnswerRules, validateAnswerRulesInSlide } from './answer-rules';

const field = (type: FieldTypes, validations: StandardFormFieldDto['validations'], properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id: 'f', index: 0, type, validations, properties });
const preset = (id: string) => FORMAT_PRESETS.find((p) => p.id === id)!.pattern;
const text = (value: string) => ({ type: 'text', text: value });

describe('which fields take answer rules', () => {
    it('text, number and multi-select choice questions', () => {
        expect(answerRuleKind(field(FieldTypes.SHORT_TEXT, {}))).toBe('text');
        expect(answerRuleKind(field(FieldTypes.LONG_TEXT, {}))).toBe('text');
        expect(answerRuleKind(field(FieldTypes.NUMBER, {}))).toBe('number');
        expect(answerRuleKind(field(FieldTypes.MULTIPLE_CHOICE, {}, { allowMultipleSelection: true }))).toBe('choices');
        expect(answerRuleKind(field(FieldTypes.MULTIPLE_CHOICE, {}))).toBeNull();
        expect(answerRuleKind(field(FieldTypes.DATE, {}))).toBeNull();
    });
});

describe('checking an answer', () => {
    it('text length, counted in characters', () => {
        const f = field(FieldTypes.SHORT_TEXT, { minLength: 3, maxLength: 5 });
        expect(checkAnswerRules(f, text('ab'))).toEqual(['TOO_SHORT']);
        expect(checkAnswerRules(f, text('abcdef'))).toEqual(['TOO_LONG']);
        expect(checkAnswerRules(f, text('abc'))).toEqual([]);
        expect(checkAnswerRules(f, text('😀😀😀'))).toEqual([]);
    });

    it('an empty answer is Required’s business, not the rules’', () => {
        expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { minLength: 3 }), undefined)).toEqual([]);
        expect(checkAnswerRules(field(FieldTypes.NUMBER, { minValue: 3 }), { number: '' })).toEqual([]);
    });

    it('format presets accept the usual ways of writing the value', () => {
        const postcode = field(FieldTypes.SHORT_TEXT, { regex: preset('postcode_nl') });
        expect(checkAnswerRules(postcode, text('1234 AB'))).toEqual([]);
        expect(checkAnswerRules(postcode, text('1234ab'))).toEqual([]);
        expect(checkAnswerRules(postcode, text('0123 AB'))).toEqual(['PATTERN']);
        const iban = field(FieldTypes.SHORT_TEXT, { regex: preset('iban') });
        expect(checkAnswerRules(iban, text('NL91 ABNA 0417 1643 00'))).toEqual([]);
        expect(checkAnswerRules(iban, text('NL91ABNA0417164300'))).toEqual([]);
        expect(checkAnswerRules(iban, text('hello'))).toEqual(['PATTERN']);
        const phone = field(FieldTypes.SHORT_TEXT, { regex: preset('phone') });
        expect(checkAnswerRules(phone, text('+31 20 123 4567'))).toEqual([]);
        expect(checkAnswerRules(phone, text('call me'))).toEqual(['PATTERN']);
        const letters = field(FieldTypes.SHORT_TEXT, { regex: preset('letters') });
        expect(checkAnswerRules(letters, text('Anne-Marie Ørsted'))).toEqual([]);
        expect(checkAnswerRules(letters, text('R2D2'))).toEqual(['PATTERN']);
    });

    it('a pattern that does not compile is ignored rather than blocking everyone', () => {
        expect(compilePattern('([')).toBeNull();
        expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex: '([' }), text('anything'))).toEqual([]);
        expect(answerRuleConflicts({ regex: '([' })).toHaveLength(1);
    });

    it('number range (0 is a real limit) and whole numbers', () => {
        const f = field(FieldTypes.NUMBER, { minValue: 0, maxValue: 10, regex: INTEGER_PATTERN });
        expect(checkAnswerRules(f, { number: -1 })).toEqual(['TOO_SMALL']);
        expect(checkAnswerRules(f, { number: '11' })).toEqual(['TOO_LARGE']);
        expect(checkAnswerRules(f, { number: '2.5' })).toEqual(['NOT_INTEGER']);
        expect(checkAnswerRules(f, { number: 0 })).toEqual([]);
    });

    it('number of options picked, counting "Other"', () => {
        const f = field(FieldTypes.MULTIPLE_CHOICE, { minChoices: 2, maxChoices: 3 }, { allowMultipleSelection: true });
        expect(checkAnswerRules(f, { choices: { values: ['a'] } })).toEqual(['TOO_FEW_CHOICES']);
        expect(checkAnswerRules(f, { choices: { values: ['a'], other: 'mine' } })).toEqual([]);
        expect(checkAnswerRules(f, { choices: { values: ['a', 'b', 'c', 'd'] } })).toEqual(['TOO_MANY_CHOICES']);
    });

    it('per page, skipping internal fields', () => {
        const a = { ...field(FieldTypes.SHORT_TEXT, { minLength: 5 }), id: 'a' };
        const b = { ...field(FieldTypes.SHORT_TEXT, { minLength: 5 }), id: 'b', internal: true };
        expect(validateAnswerRulesInSlide([a, b], { a: text('x'), b: text('x') })).toEqual({ a: ['TOO_SHORT'] });
    });
});

describe('telling people about the rules', () => {
    const t = (key: string, options?: Record<string, unknown>) => `${key}${options ? ' ' + JSON.stringify(options) : ''}`;

    it('respondent messages name the limit or the expected format', () => {
        expect(answerRuleMessage(field(FieldTypes.SHORT_TEXT, { minLength: 3 }), 'TOO_SHORT', t)).toBe('RULE.TOO_SHORT {"count":3}');
        expect(answerRuleMessage(field(FieldTypes.SHORT_TEXT, { regex: preset('postcode_nl') }), 'PATTERN', t)).toBe('RULE.FORMAT_POSTCODE_NL {"example":"1234 AB"}');
        expect(answerRuleMessage(field(FieldTypes.SHORT_TEXT, { regex: '^x$' }), 'PATTERN', t)).toBe('RULE.PATTERN');
        expect(answerRuleMessage(field(FieldTypes.NUMBER, { maxValue: 9 }), 'TOO_LARGE', t)).toBe('RULE.TOO_LARGE {"max":9}');
    });

    it('the builder summary is plain language', () => {
        expect(summarizeAnswerRules(field(FieldTypes.SHORT_TEXT, { minLength: 2, maxLength: 40, regex: preset('iban') }))).toEqual(['Answer is between 2 and 40 characters.', 'Answer must be an IBAN, e.g. NL91 ABNA 0417 1643 00.']);
        expect(summarizeAnswerRules(field(FieldTypes.NUMBER, { minValue: 1, regex: INTEGER_PATTERN }))).toEqual(['Number of at least 1.', 'Whole numbers only.']);
        expect(summarizeAnswerRules(field(FieldTypes.MULTIPLE_CHOICE, { maxChoices: 2 }, { allowMultipleSelection: true }))).toEqual(['Pick at most 2 options.']);
        expect(summarizeAnswerRules(field(FieldTypes.SHORT_TEXT, {}))).toEqual([]);
        expect(presetForPattern('^custom$')).toBeUndefined();
    });

    it('contradictory limits are pointed out', () => {
        expect(answerRuleConflicts({ minLength: 5, maxLength: 2 })).toEqual(['The minimum length is more than the maximum.']);
        expect(answerRuleConflicts({ minValue: 1, maxValue: 1 })).toEqual([]);
    });
});

describe('the pattern length cap', () => {
    it('is the form spec cap (200), which the server shares', () => {
        const schema = JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/form-spec-v1.schema.json'), 'utf-8'));
        const caps: number[] = [];
        const walk = (node: any) => {
            if (!node || typeof node !== 'object') return;
            if (node.pattern?.anyOf) node.pattern.anyOf.forEach((option: any) => typeof option.maxLength === 'number' && caps.push(option.maxLength));
            Object.values(node).forEach(walk);
        };
        walk(schema);
        expect(PATTERN_MAX_LENGTH).toBe(200);
        expect(caps.length).toBeGreaterThan(0);
        expect(new Set(caps)).toEqual(new Set([PATTERN_MAX_LENGTH]));
    });

    it('a stored pattern over the cap is pointed out', () => {
        expect(answerRuleConflicts({ regex: 'a'.repeat(PATTERN_MAX_LENGTH) })).toEqual([]);
        expect(answerRuleConflicts({ regex: 'a'.repeat(PATTERN_MAX_LENGTH + 1) })).toEqual(['The pattern is longer than 200 characters. Shorten it.']);
    });
});
