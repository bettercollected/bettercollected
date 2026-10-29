import { readFileSync } from 'fs';
import { resolve } from 'path';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import {
    FORMAT_PRESETS,
    INTEGER_PATTERN,
    PATTERN_MAX_LENGTH,
    PATTERN_TEST_MAX_LENGTH,
    answerRuleConflicts,
    answerRuleKind,
    answerRuleMessage,
    checkAnswerRules,
    compilePattern,
    patternBreaks,
    patternProblem,
    presetForPattern,
    summarizeAnswerRules,
    validateAnswerRulesInSlide
} from './answer-rules';

const UNSAFE_CASES = (
    JSON.parse(readFileSync(resolve(__dirname, '../../../docs/spec/pattern-safety.cases.json'), 'utf-8')) as {
        unsafe: Array<{ pattern: string; hazard: string }>;
    }
).unsafe;

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

describe('a pattern whose shape can freeze a browser', () => {
    // timing-free: the engine's `test` is watched, never raced. The hazardous patterns come from the
    // shared case table rather than being written here, so no such pattern sits in this source.
    const spy = () => vi.spyOn(RegExp.prototype, 'test');
    afterEach(() => vi.restoreAllMocks());
    const answerThatFreezes = `${'a'.repeat(5000)}b`;
    const unsafe = UNSAFE_CASES.map((c) => c.pattern);
    const nested = UNSAFE_CASES.find((c) => c.hazard === 'nested_repeat')!.pattern;

    it('never reaches the backtracking RegExp.test, for text and number questions', () => {
        const test = spy();
        expect(compilePattern(nested)).toBeNull();
        expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex: nested }), text(answerThatFreezes))).toEqual([]);
        // every unsafe shape in the shared table, on a text and a long-text question
        for (const regex of unsafe) {
            expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex }), text('a'.repeat(28)))).toEqual([]);
            expect(checkAnswerRules(field(FieldTypes.LONG_TEXT, { regex }), text(answerThatFreezes))).toEqual([]);
        }
        const digits = unsafe.find((p) => p.includes('\\d'))!;
        expect(checkAnswerRules(field(FieldTypes.NUMBER, { regex: digits }), { type: 'number', number: '1111111111111111111111x' })).toEqual([]);
        expect(validateAnswerRulesInSlide([field(FieldTypes.SHORT_TEXT, { regex: nested })], { f: text(answerThatFreezes) })).toEqual({});
        expect(test).not.toHaveBeenCalled();
    });

    it('is not tested against a long answer either: the server checks it with RE2', () => {
        const test = spy();
        const rules = field(FieldTypes.SHORT_TEXT, { regex: '^[a-z]+$' });
        // at the cap it is tested, over it left to the server
        expect(checkAnswerRules(rules, text('1'.repeat(PATTERN_TEST_MAX_LENGTH)))).toEqual(['PATTERN']);
        expect(test).toHaveBeenCalledTimes(1);
        expect(checkAnswerRules(rules, text('1'.repeat(PATTERN_TEST_MAX_LENGTH + 1)))).toEqual([]);
        expect(checkAnswerRules(field(FieldTypes.NUMBER, { regex: INTEGER_PATTERN }), { type: 'number', number: '1.'.repeat(PATTERN_TEST_MAX_LENGTH) })).toEqual([]);
        expect(patternBreaks('^[a-z]+$', 'x'.repeat(PATTERN_TEST_MAX_LENGTH + 1))).toBe(false);
        expect(test).toHaveBeenCalledTimes(1);
    });

    it('does not stop a safe pattern from being tested', () => {
        const test = spy();
        expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex: preset('postcode_nl') }), text('nope'))).toEqual(['PATTERN']);
        expect(test).toHaveBeenCalledTimes(1);
    });

    it('checks the shape before the lenient compile too: a pattern only the non-u compile accepts', () => {
        // \- outside a class is an error with the u flag and fine without it
        expect(() => new RegExp('^a+\\-$', 'u')).toThrow();
        expect(compilePattern('^a+\\-$')).not.toBeNull();
        // an unsafe shape that also only compiles without the u flag (from the shared table)
        const lenientOnly = unsafe.find((p) => p.endsWith('\\-$'))!;
        expect(() => new RegExp(lenientOnly, 'u')).toThrow();
        expect(compilePattern(lenientOnly)).toBeNull();
    });

    it('is told apart from one that does not compile', () => {
        expect(patternProblem(nested)).toBe('nested_repeat');
        expect(patternProblem('([')).toBe('invalid');
        expect(patternProblem('^[a-z]+$')).toBeNull();
        expect(patternProblem(undefined)).toBeNull();
        // the shape is pointed out next to the pattern box, not in the conflicts
        expect(answerRuleConflicts({ regex: nested })).toEqual([]);
    });

    it('keeps the presets and the whole-number rule testable', () => {
        for (const p of FORMAT_PRESETS) expect(compilePattern(p.pattern)).not.toBeNull();
        expect(compilePattern(INTEGER_PATTERN)).not.toBeNull();
    });
});
