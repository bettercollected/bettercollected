import { readFileSync } from 'fs';
import { resolve } from 'path';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import {
    FORMAT_PRESETS,
    INTEGER_PATTERN,
    PATTERN_MAX_LENGTH,
    answerRuleConflicts,
    answerRuleKind,
    answerRuleMessage,
    browserChecksPattern,
    checkAnswerRules,
    compilePattern,
    presetForPattern,
    summarizeAnswerRules,
    validateAnswerRulesInSlide
} from './answer-rules';

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

    it('a custom pattern is not tested here, whatever it is: the server checks it on submit', () => {
        for (const regex of ['([', '^[a-z]+$', '^(a+)+$', '^(?=a)b$']) {
            expect(compilePattern(regex)).toBeNull();
            expect(browserChecksPattern(regex)).toBe(false);
            expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex }), text('9 not a match'))).toEqual([]);
        }
        expect(answerRuleConflicts({ regex: '([' })).toEqual([]);
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

describe('a pattern a creator wrote never runs in the browser', () => {
    afterEach(() => vi.restoreAllMocks());
    const custom = ['^(a+)+$', '^[a-z]+$', '(?i)abc', '^(?:A(?:\\A)?)+$', '^(?:\\u{1F600}|\\ud83d\\ude00)+$', '^a+\\-$'];
    const slow = `${'a'.repeat(5000)}!`;

    it('is neither compiled nor tested, on a text or a number question or a slide', () => {
        const test = vi.spyOn(RegExp.prototype, 'test');
        const compiled: string[] = [];
        const Original = RegExp;
        // every RegExp built while the answers are checked (on the page or on a slide)
        vi.stubGlobal(
            'RegExp',
            class extends Original {
                constructor(pattern: string | RegExp, flags?: string) {
                    super(pattern, flags);
                    compiled.push(String(pattern));
                }
            }
        );
        try {
            for (const regex of custom) {
                expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex }), text(slow))).toEqual([]);
                expect(checkAnswerRules(field(FieldTypes.LONG_TEXT, { regex }), text('x'))).toEqual([]);
                expect(checkAnswerRules(field(FieldTypes.NUMBER, { regex }), { type: 'number', number: '12x' })).toEqual([]);
                expect(validateAnswerRulesInSlide([field(FieldTypes.SHORT_TEXT, { regex })], { f: text(slow) })).toEqual({});
            }
        } finally {
            vi.unstubAllGlobals();
        }
        expect(test).not.toHaveBeenCalled();
        expect(compiled.filter((source) => custom.includes(source))).toEqual([]);
    });

    it('while the presets and whole numbers are still checked live, by identity', () => {
        const test = vi.spyOn(RegExp.prototype, 'test');
        expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex: preset('postcode_nl') }), text('nope'))).toEqual(['PATTERN']);
        expect(checkAnswerRules(field(FieldTypes.SHORT_TEXT, { regex: preset('postcode_nl') }), text('1234 AB'))).toEqual([]);
        expect(checkAnswerRules(field(FieldTypes.NUMBER, { regex: INTEGER_PATTERN }), { type: 'number', number: '1.5' })).toEqual(['NOT_INTEGER']);
        expect(test).toHaveBeenCalledTimes(3);
        // a pattern that only looks like a preset is a custom one
        expect(browserChecksPattern(`${preset('postcode_nl')} `)).toBe(false);
        expect(browserChecksPattern(preset('iban'))).toBe(true);
        expect(FORMAT_PRESETS.every((p) => browserChecksPattern(p.pattern))).toBe(true);
    });
});

describe('date range answers', () => {
    const range = (start?: string | null, end?: string | null) => ({ type: 'date_range', date_range: { start, end } });
    const f = field(FieldTypes.DATE_RANGE, {});

    it('is a kind of its own, with no settings beyond its date rules', () => {
        expect(answerRuleKind(f)).toBe('date_range');
        expect(summarizeAnswerRules(f)).toEqual([]);
    });

    it('takes a start and a later end, an end on the start included', () => {
        expect(checkAnswerRules(f, range('2026-11-03', '2026-11-07'))).toEqual([]);
        expect(checkAnswerRules(f, range('2026-11-03', '2026-11-03'))).toEqual([]);
        expect(checkAnswerRules(f, range('2026-12-30', '2027-01-02'))).toEqual([]);
        expect(checkAnswerRules(f, range('2024-02-29', '2024-03-01'))).toEqual([]);
    });

    it('wants both ends once one is given', () => {
        expect(checkAnswerRules(f, range('2026-11-03', undefined))).toEqual(['REQUIRED']);
        expect(checkAnswerRules(f, range(undefined, '2026-11-07'))).toEqual(['REQUIRED']);
        expect(checkAnswerRules(f, range('2026-11-03', ''))).toEqual(['REQUIRED']);
        expect(checkAnswerRules(f, range('2026-11-03', null))).toEqual(['REQUIRED']);
    });

    it('leaves an empty range to Required', () => {
        expect(checkAnswerRules(f, undefined)).toEqual([]);
        expect(checkAnswerRules(f, range('', ''))).toEqual([]);
        expect(checkAnswerRules(f, range(undefined, undefined))).toEqual([]);
        expect(checkAnswerRules(f, { type: 'date_range' })).toEqual([]);
    });

    it('refuses an end before the start', () => {
        expect(checkAnswerRules(f, range('2026-11-07', '2026-11-03'))).toEqual(['RANGE_ORDER']);
    });

    it('refuses days that are not real days written YYYY-MM-DD', () => {
        expect(checkAnswerRules(f, range('2026-02-30', '2026-03-05'))).toEqual(['FORMAT']);
        expect(checkAnswerRules(f, range('03-11-2026', '2026-11-07'))).toEqual(['FORMAT']);
        expect(checkAnswerRules(f, range('2026-1-03', '2026-11-07'))).toEqual(['FORMAT']);
    });

    it('is the server’s problem when the answer is not a range at all', () => {
        expect(checkAnswerRules(f, { type: 'date', date: '2026-11-03' })).toEqual([]);
        expect(checkAnswerRules(f, { type: 'date_range', date_range: { start: 5, end: 6 } })).toEqual([]);
        expect(checkAnswerRules(f, { type: 'date_range', date_range: { start: '2026-11-03', end: '2026-11-07', extra: 'x' } })).toEqual([]);
    });

    it('says what is wrong, in the respondent’s language keys', () => {
        const t = (key: string, options?: Record<string, unknown>) => `${key}${options ? ' ' + JSON.stringify(options) : ''}`;
        expect(answerRuleMessage(f, 'RANGE_ORDER', t)).toBe('RULE.RANGE_ORDER');
        expect(answerRuleMessage(f, 'REQUIRED', t)).toBe('RULE.RANGE_INCOMPLETE');
        expect(answerRuleMessage(f, 'FORMAT', t)).toBe('RULE.FORMAT_RANGE');
    });

    it('is checked in a repeating group item too', () => {
        const group = { id: 'g', index: 0, type: FieldTypes.GROUP, properties: { repeat: { minItems: 1, maxItems: 3 }, fields: [{ ...f, id: 'stay' }] } } as StandardFormFieldDto;
        const answers = { g: { type: 'group', items: [{ stay: range('2026-11-07', '2026-11-03') }] } };
        expect(validateAnswerRulesInSlide([group], answers)).toEqual({ 'stay::0': ['RANGE_ORDER'] });
    });
});

describe('tags answers', () => {
    const tags = (...list: unknown[]) => ({ type: 'tags', tags: list });
    const f = (validations: StandardFormFieldDto['validations'] = {}) => field(FieldTypes.TAGS, validations);

    it('is a kind of its own', () => {
        expect(answerRuleKind(f())).toBe('tags');
    });

    it('takes well-formed, different tags', () => {
        expect(checkAnswerRules(f(), tags('vegan', 'gluten free', 'café'))).toEqual([]);
        expect(checkAnswerRules(f(), tags('one'))).toEqual([]);
    });

    it('leaves no tags to Required', () => {
        expect(checkAnswerRules(f({ minChoices: 2 }), undefined)).toEqual([]);
        expect(checkAnswerRules(f({ minChoices: 2 }), tags())).toEqual([]);
    });

    it.each([
        ['an empty tag', ''],
        ['a space before', ' a'],
        ['a space after', 'a '],
        ['a comma', 'a,b'],
        ['a semicolon', 'a;b'],
        ['a tab', 'a\tb'],
        ['a line break', 'a\nb']
    ])('refuses %s', (_name, tag) => {
        expect(checkAnswerRules(f(), tags('ok', tag))).toEqual(['FORMAT']);
    });

    it('holds a tag to the longest the question allows, never above 40 characters', () => {
        expect(checkAnswerRules(f(), tags('a'.repeat(40)))).toEqual([]);
        expect(checkAnswerRules(f(), tags('a'.repeat(41)))).toEqual(['TOO_LONG']);
        expect(checkAnswerRules(f({ maxLength: 5 }), tags('abcde'))).toEqual([]);
        expect(checkAnswerRules(f({ maxLength: 5 }), tags('abcdef'))).toEqual(['TOO_LONG']);
        expect(checkAnswerRules(f({ maxLength: 100 }), tags('a'.repeat(41)))).toEqual(['TOO_LONG']);
        // characters, not UTF-16 units
        expect(checkAnswerRules(f({ maxLength: 2 }), tags('😀😀'))).toEqual([]);
    });

    it('refuses an entry that is not text, whatever else is in the list', () => {
        for (const junk of [null, undefined, 5, [], {}]) {
            expect(checkAnswerRules(f(), tags(junk))).toEqual(['FORMAT']);
            expect(checkAnswerRules(f(), tags('ok', junk))).toEqual(['FORMAT']);
        }
        expect(checkAnswerRules(f(), tags(''))).toEqual(['FORMAT']);
    });

    it('takes a precomposed and a decomposed letter for the same tag', () => {
        expect(checkAnswerRules(f(), tags('caf\u00e9', 'cafe\u0301'))).toEqual(['DUPLICATE']);
        expect(checkAnswerRules(f(), tags('cafe', 'caf\u00e9'))).toEqual([]);
    });

    it('refuses a tag written again, ignoring case', () => {
        expect(checkAnswerRules(f(), tags('Vegan', 'vegan'))).toEqual(['DUPLICATE']);
        expect(checkAnswerRules(f(), tags('a', 'b', 'B'))).toEqual(['DUPLICATE']);
        expect(checkAnswerRules(f(), tags('a', 'a '.trim() + 'b'))).toEqual([]);
    });

    it('holds the number of tags to the question’s own limits, never above 30', () => {
        expect(checkAnswerRules(f({ minChoices: 2 }), tags('a'))).toEqual(['TOO_FEW_CHOICES']);
        expect(checkAnswerRules(f({ minChoices: 2 }), tags('a', 'b'))).toEqual([]);
        expect(checkAnswerRules(f({ maxChoices: 2 }), tags('a', 'b', 'c'))).toEqual(['TOO_MANY_CHOICES']);
        expect(checkAnswerRules(f({ maxChoices: 2 }), tags('a', 'b'))).toEqual([]);
        const many = (n: number) => Array.from({ length: n }, (_v, i) => `t${i}`);
        expect(checkAnswerRules(f(), tags(...many(30)))).toEqual([]);
        expect(checkAnswerRules(f(), tags(...many(31)))).toEqual(['TOO_MANY_CHOICES']);
        expect(checkAnswerRules(f({ maxChoices: 50 }), tags(...many(31)))).toEqual(['TOO_MANY_CHOICES']);
    });

    it('lists every problem it finds', () => {
        expect(checkAnswerRules(f({ maxChoices: 2 }), tags('a', 'A', 'b'))).toEqual(['DUPLICATE', 'TOO_MANY_CHOICES']);
        expect(checkAnswerRules(f({ maxLength: 2 }), tags('abc', ' '))).toEqual(['FORMAT', 'TOO_LONG']);
    });

    it('is the server’s problem when the answer is not a list of texts', () => {
        expect(checkAnswerRules(f(), { type: 'tags', tags: 'a' })).toEqual([]);
        expect(checkAnswerRules(f(), tags('a', 3))).toEqual(['FORMAT']);
        expect(checkAnswerRules(f(), { type: 'text', text: 'a' })).toEqual([]);
    });

    it('says what is wrong, with the effective limits', () => {
        const t = (key: string, options?: Record<string, unknown>) => `${key}${options ? ' ' + JSON.stringify(options) : ''}`;
        expect(answerRuleMessage(f({ maxLength: 12 }), 'TOO_LONG', t)).toBe('RULE.TAG_TOO_LONG {"count":12}');
        expect(answerRuleMessage(f({ maxLength: 99 }), 'TOO_LONG', t)).toBe('RULE.TAG_TOO_LONG {"count":40}');
        expect(answerRuleMessage(f({ minChoices: 2 }), 'TOO_FEW_CHOICES', t)).toBe('RULE.TOO_FEW_TAGS {"count":2}');
        expect(answerRuleMessage(f({ maxChoices: 3 }), 'TOO_MANY_CHOICES', t)).toBe('RULE.TOO_MANY_TAGS {"count":3}');
        expect(answerRuleMessage(f(), 'TOO_MANY_CHOICES', t)).toBe('RULE.TOO_MANY_TAGS {"count":30}');
        expect(answerRuleMessage(f(), 'DUPLICATE', t)).toBe('RULE.TAG_DUPLICATE');
        expect(answerRuleMessage(f(), 'FORMAT', t)).toBe('RULE.FORMAT_TAGS');
    });

    it('the builder summary names the limits', () => {
        expect(summarizeAnswerRules(f({ minChoices: 1, maxChoices: 5, maxLength: 20 }))).toEqual(['Enter between 1 and 5 tags.', 'Each tag is at most 20 characters.']);
        expect(summarizeAnswerRules(f())).toEqual(['Each tag is at most 40 characters.']);
    });
});
