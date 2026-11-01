import i18n from 'i18next';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { IFormFieldValidation } from '@app/models/types/form-builder-shared';
import { addressProblems } from '@app/utils/address';
import { countryName, questionCountries } from '@app/utils/countries';
import { currencyDecimals, formatAmount, isCurrencyCode, parseAmount } from '@app/utils/currency';
import { isDay } from '@app/utils/iso-date';
import { rawDateRange } from '@app/utils/date-range';
import { SIGNATURE_NAME_MAX, answerSignature, signatureProblem, signatureShape } from '@app/utils/signature';
import { TAGS_MAX, TAG_LENGTH_MAX, duplicateIndex, isTag, tagLength } from '@app/utils/tags';
import { isTime, minutesOf } from '@app/utils/time-of-day';
import type { LogicSources } from '@app/utils/conditional-logic';
import type { OptionStates } from '@app/utils/option-logic';
import { getDisplayedItemCount, getGroupChildren, getGroupItems, getItemHiddenChildIds, isRepeatingGroup, scopedFieldId } from '@app/utils/repeating-groups';

/**
 * "Answer rules": the limits a creator puts on an answer beyond Required,
 * stored in the field's `validations` (common StandardFieldValidations:
 * min/max length, min/max value, min/max choices, regex).
 *
 * - Short and long text: length limits and a format (a regex, usually from
 *   a preset).
 * - Number: lowest and highest value, and "whole numbers only" (stored as
 *   the INTEGER_PATTERN regex, checked against the number as typed).
 * - Multiple choice with multiple selection: how many options to pick.
 * - Time: the earliest and latest time (`minTime`, `maxTime`, in the
 *   properties) and the format (HH:MM).
 * - Day (typed as day, month and year): the date must be a real one.
 * - Currency: the currency must be one of the question's (EUR when it names
 *   none), the amount a plain decimal with the currency's own decimals, and
 *   within the lowest and highest value.
 * - Date range: both days once either is given, well-formed, the end not
 *   before the start (each end also meets the question's date rules: utils/date-rules.ts).
 * - Tags: each tag trimmed, not empty, without `,` `;` or control characters,
 *   at most the question's longest tag (never above TAG_LENGTH_MAX), no two the
 *   same ignoring case, and their number within the fewest and most (never
 *   above TAGS_MAX).
 *
 * - Address: the street, house number, postcode and city once any part is given
 *   (and the country when the question allows several), a Dutch postcode as
 *   `1234 AB` and a Dutch house number of digits, a country the question allows
 *   (utils/address.ts, the twin of the server's common `address.py`).
 * - Signature: a typed name is well formed (trimmed, in form C, no hidden or
 *   control characters, at most SIGNATURE_NAME_MAX characters); a drawn
 *   signature names its image. It has no limits of its own to set.
 *
 * An empty answer is never checked here: whether one is needed is what
 * Required says.
 */

export type AnswerRuleKind = 'text' | 'number' | 'choices' | 'time' | 'day' | 'currency' | 'date_range' | 'tags' | 'address';

export type AnswerRuleProblem = 'TOO_SHORT' | 'TOO_LONG' | 'PATTERN' | 'TOO_SMALL' | 'TOO_LARGE' | 'NOT_INTEGER' | 'TOO_FEW_CHOICES' | 'TOO_MANY_CHOICES' | 'FORMAT' | 'CURRENCY' | 'REQUIRED' | 'RANGE_ORDER' | 'DUPLICATE' | 'COUNTRY' | 'SIGNATURE_IMAGE';

/**
 * What the problems are, by the server's rule code (lower case). `REQUIRED` is
 * a date range with only one end given, or an address with a part missing; it is not listed in ANSWER_RULE_PROBLEMS
 * because the server and the page also use it for an unanswered required question.
 */
export const ANSWER_RULE_PROBLEMS: ReadonlyArray<AnswerRuleProblem> = ['TOO_SHORT', 'TOO_LONG', 'PATTERN', 'TOO_SMALL', 'TOO_LARGE', 'NOT_INTEGER', 'TOO_FEW_CHOICES', 'TOO_MANY_CHOICES', 'FORMAT', 'CURRENCY', 'RANGE_ORDER', 'DUPLICATE', 'COUNTRY', 'SIGNATURE_IMAGE'];

/** "Whole numbers only" on a number question. */
export const INTEGER_PATTERN = '^-?\\d+$';

export type FormatPresetId = 'postcode_nl' | 'iban' | 'phone' | 'letters';

export interface FormatPreset {
    id: FormatPresetId;
    label: string;
    /** What the summary says ("must be a Dutch postcode"). */
    summary: string;
    pattern: string;
    example: string;
}

/**
 * Common formats. The patterns are deliberately forgiving about spacing and
 * case: they catch typos, they are not a full check of the value.
 */
export const FORMAT_PRESETS: ReadonlyArray<FormatPreset> = [
    { id: 'postcode_nl', label: 'Dutch postcode', summary: 'a Dutch postcode', pattern: '^[1-9][0-9]{3} ?[A-Za-z]{2}$', example: '1234 AB' },
    { id: 'iban', label: 'IBAN', summary: 'an IBAN', pattern: '^[A-Za-z]{2}[0-9]{2}(?: ?[A-Za-z0-9]){11,30}$', example: 'NL91 ABNA 0417 1643 00' },
    { id: 'phone', label: 'Phone number', summary: 'a phone number', pattern: '^\\+?[0-9][0-9 ()-]{5,19}$', example: '+31 20 123 4567' },
    { id: 'letters', label: 'Letters only', summary: 'letters only', pattern: "^[\\p{L} '-]+$", example: 'Anne-Marie' }
];

/**
 * Patterns longer than this are not accepted from the builder. The same cap
 * as the form spec (common form_spec PATTERN_MAX_LENGTH, the schema's
 * maxLength) and the server, which does not enforce a longer pattern.
 */
export const PATTERN_MAX_LENGTH = 200;

export function presetForPattern(pattern: string | undefined | null): FormatPreset | undefined {
    return pattern ? FORMAT_PRESETS.find((preset) => preset.pattern === pattern) : undefined;
}

const KNOWN_PATTERNS: Map<string, RegExp> = new Map([...FORMAT_PRESETS.map((preset) => preset.pattern), INTEGER_PATTERN].map((pattern) => [pattern, new RegExp(pattern, 'u')]));

/**
 * The RegExp for a pattern this browser may test answers with: only our own
 * fixed ones, the format presets and "whole numbers only", looked up by
 * exact identity (never by analysing the string). A pattern a creator wrote
 * is not tested here at all: it could take a backtracking engine very long,
 * and no check of its shape can promise it does not. The server matches it
 * with RE2 (linear time) when the answer is submitted, and the respondent is
 * taken back to the question with the message (utils/server-answer-errors.ts).
 */
export function compilePattern(pattern: string | undefined | null): RegExp | null {
    return (pattern && KNOWN_PATTERNS.get(pattern)) || null;
}

/** Whether this browser checks the pattern itself (a preset), or leaves it to the server. */
export const browserChecksPattern = (pattern: string | undefined | null): boolean => compilePattern(pattern) !== null;

/** Which kind of answer rules a field takes, if any. */
export function answerRuleKind(field: Pick<StandardFormFieldDto, 'type' | 'properties'> | undefined | null): AnswerRuleKind | null {
    switch (field?.type) {
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LONG_TEXT:
            return 'text';
        case FieldTypes.NUMBER:
            return 'number';
        case FieldTypes.MULTIPLE_CHOICE:
            return field.properties?.allowMultipleSelection ? 'choices' : null;
        case FieldTypes.TIME:
            return 'time';
        case FieldTypes.DAY:
            return 'day';
        case FieldTypes.CURRENCY:
            return 'currency';
        case FieldTypes.DATE_RANGE:
            return 'date_range';
        case FieldTypes.TAGS:
            return 'tags';
        case FieldTypes.ADDRESS:
            return 'address';
        default:
            return null;
    }
}

const isSet = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

function answerText(answer: any): string | undefined {
    const text = answer?.text;
    return typeof text === 'string' && text.length ? text : undefined;
}

function answerNumber(answer: any): { value: number; typed: string } | undefined {
    const raw = answer?.number;
    if (raw === undefined || raw === null || raw === '') return undefined;
    const typed = String(raw).trim();
    const value = Number(typed);
    return Number.isFinite(value) ? { value, typed } : undefined;
}

/** A currency answer is `{ code: text, amount: text }` (either may be missing); another shape is the server's "type" problem. */
function currencyShape(value: any): value is { code?: string; amount?: string } {
    return !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).every((key) => key === 'code' || key === 'amount') && Object.values(value).every((v) => v === undefined || v === null || typeof v === 'string');
}

/** A date range answer is `{ start: text, end: text }` (either may be missing); another shape is the server's "type" problem. */
function dateRangeShape(value: any): value is { start?: string | null; end?: string | null } {
    return !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).every((key) => key === 'start' || key === 'end') && Object.values(value).every((v) => v === undefined || v === null || typeof v === 'string');
}

/** Is only one end of a date range given? (the answer is not finished: `REQUIRED`) */
export function isRangeHalfFilled(answer: any): boolean {
    const value = rawDateRange(answer);
    return dateRangeShape(value) && !!value.start !== !!value.end;
}

/** The number of characters one tag of this question may have, and the fewest and most tags it takes (the hard caps apply even when the question's own limits are higher). */
export function tagLimits(field: Pick<StandardFormFieldDto, 'validations'> | undefined | null): { length: number; fewest: number; most: number } {
    const rules: IFormFieldValidation = field?.validations ?? {};
    return {
        length: isSet(rules.maxLength) ? Math.min(TAG_LENGTH_MAX, Math.max(Math.trunc(rules.maxLength), 0)) : TAG_LENGTH_MAX,
        fewest: isSet(rules.minChoices) ? Math.trunc(rules.minChoices) : 0,
        most: isSet(rules.maxChoices) ? Math.min(TAGS_MAX, Math.trunc(rules.maxChoices)) : TAGS_MAX
    };
}

function answerChoiceCount(answer: any): number | undefined {
    const choices = answer?.choices;
    if (!choices) return undefined;
    const count = (choices.values?.length ?? 0) + (typeof choices.other === 'string' && choices.other.trim() ? 1 : 0);
    return count > 0 ? count : undefined;
}

/** The currencies a currency question offers: its own list, else the euro. */
export const questionCurrencies = (field: Pick<StandardFormFieldDto, 'properties'> | undefined | null): string[] => (field?.properties?.currencies?.length ? field.properties.currencies : ['EUR']);

/** The rules an answer breaks (empty when it keeps them all, or is empty). */
export function checkAnswerRules(field: StandardFormFieldDto, answer: any, options?: OptionStates): AnswerRuleProblem[] {
    const rules: IFormFieldValidation = field?.validations ?? {};
    const problems: AnswerRuleProblem[] = [];
    if (field?.type === FieldTypes.SIGNATURE) {
        // a typed name that is not well formed, or a drawn signature without an image (the server says "type" for another shape)
        const value = answer?.signature;
        if (value === undefined || value === null || !signatureShape(value)) return [];
        const problem = signatureProblem(answerSignature(answer) ?? {});
        return problem ? [problem] : [];
    }
    switch (answerRuleKind(field)) {
        case 'text': {
            const text = answerText(answer);
            if (text === undefined) break;
            // Count characters as people do (an emoji is one).
            const length = Array.from(text).length;
            if (isSet(rules.minLength) && length < rules.minLength) problems.push('TOO_SHORT');
            if (isSet(rules.maxLength) && length > rules.maxLength) problems.push('TOO_LONG');
            const pattern = compilePattern(rules.regex);
            if (pattern && !pattern.test(text.trim())) problems.push('PATTERN');
            break;
        }
        case 'number': {
            const number = answerNumber(answer);
            if (!number) break;
            if (isSet(rules.minValue) && number.value < rules.minValue) problems.push('TOO_SMALL');
            if (isSet(rules.maxValue) && number.value > rules.maxValue) problems.push('TOO_LARGE');
            if (rules.regex) {
                const pattern = compilePattern(rules.regex);
                if (pattern && !pattern.test(number.typed)) problems.push(rules.regex === INTEGER_PATTERN ? 'NOT_INTEGER' : 'PATTERN');
            }
            break;
        }
        case 'choices': {
            const count = answerChoiceCount(answer);
            if (count === undefined) break;
            // held to what the question offers (choice logic can offer fewer options than the minimum)
            const minimum = isSet(rules.minChoices) ? (options ? options.minChoices(field.id, rules.minChoices) : rules.minChoices) : undefined;
            if (isSet(minimum) && count < minimum) problems.push('TOO_FEW_CHOICES');
            if (isSet(rules.maxChoices) && count > rules.maxChoices) problems.push('TOO_MANY_CHOICES');
            break;
        }
        case 'time': {
            const time = answer?.time;
            if (typeof time !== 'string' || !time) break;
            if (!isTime(time)) return ['FORMAT'];
            const { minTime, maxTime } = field.properties ?? {};
            if (isTime(minTime) && minutesOf(time) < minutesOf(minTime)) problems.push('TOO_SMALL');
            if (isTime(maxTime) && minutesOf(time) > minutesOf(maxTime)) problems.push('TOO_LARGE');
            break;
        }
        case 'day': {
            const date = answer?.date;
            if (typeof date === 'string' && date && !isDay(date)) problems.push('FORMAT');
            break;
        }
        case 'currency': {
            const value = answer?.currency;
            if (!currencyShape(value)) break;
            const { code, amount } = value;
            if (!code && !amount) break;
            if (typeof code !== 'string' || !isCurrencyCode(code)) return ['FORMAT'];
            if (!questionCurrencies(field).includes(code)) return ['CURRENCY'];
            const parsed = parseAmount(amount, code);
            if (parsed === undefined) return ['FORMAT'];
            // an amount is not below zero unless the question's lowest amount says so
            if (parsed < (isSet(rules.minValue) ? rules.minValue : 0)) problems.push('TOO_SMALL');
            if (isSet(rules.maxValue) && parsed > rules.maxValue) problems.push('TOO_LARGE');
            break;
        }
        case 'date_range': {
            const value = rawDateRange(answer);
            if (!dateRangeShape(value)) break;
            const { start, end } = { start: value.start || '', end: value.end || '' };
            if (!start && !end) break;
            // both ends are needed once it is answered
            if (!start || !end) return ['REQUIRED'];
            if (!isDay(start) || !isDay(end)) return ['FORMAT'];
            if (end < start) problems.push('RANGE_ORDER');
            break;
        }
        case 'address': {
            // the rules of utils/address.ts; the server says "type" for another shape
            for (const rule of addressProblems(answer?.address, questionCountries(field))) problems.push(rule === 'required' ? 'REQUIRED' : rule === 'country' ? 'COUNTRY' : rule === 'too_long' ? 'TOO_LONG' : 'FORMAT');
            break;
        }
        case 'tags': {
            const tags = answer?.tags;
            if (!Array.isArray(tags) || !tags.length) break;
            // text only (the server says "type"; the browser never builds anything else)
            if (!tags.every((tag) => typeof tag === 'string')) return ['FORMAT'];
            const limits = tagLimits(field);
            if (!tags.every(isTag)) problems.push('FORMAT');
            if (tags.some((tag) => tagLength(tag) > limits.length)) problems.push('TOO_LONG');
            if (duplicateIndex(tags) !== null) problems.push('DUPLICATE');
            if (tags.length < limits.fewest) problems.push('TOO_FEW_CHOICES');
            if (tags.length > limits.most) problems.push('TOO_MANY_CHOICES');
            break;
        }
    }
    return problems;
}

/**
 * The answer-rule problems of the fields on a page, keyed by field id (the
 * same shape as validateSlide's), for the fields the respondent sees. Inside
 * a repeating group every displayed item is checked, keyed by the item-scoped
 * id its question renders under, skipping questions hidden in that item (the
 * server checks items the same way).
 */
export function validateAnswerRulesInSlide(fields: ReadonlyArray<StandardFormFieldDto> | undefined, answers: Record<string, any>, sources?: LogicSources, locked?: ReadonlySet<string>, options?: OptionStates): Record<string, AnswerRuleProblem[]> {
    const invalid: Record<string, AnswerRuleProblem[]> = {};
    (fields ?? []).forEach((field) => {
        if (field.internal) return;
        if (isRepeatingGroup(field)) {
            const items = getGroupItems(answers, field.id);
            const count = getDisplayedItemCount(field, answers);
            for (let index = 0; index < count; index++) {
                const hidden = getItemHiddenChildIds(field, answers, index, sources);
                getGroupChildren(field).forEach((child) => {
                    if (child.internal || hidden.has(child.id)) return;
                    const problems = checkAnswerRules(child, items[index]?.[child.id]);
                    if (problems.length) invalid[scopedFieldId(child.id, index)] = problems;
                });
            }
            return;
        }
        // The form's own value (a field rule sets or locks it): not the respondent's to correct.
        if (locked?.has(field.id)) return;
        const problems = checkAnswerRules(field, answers[field.id], options);
        if (problems.length) invalid[field.id] = problems;
    });
    return invalid;
}

export const isAnswerRuleProblem = (code: unknown): code is AnswerRuleProblem => typeof code === 'string' && (ANSWER_RULE_PROBLEMS as ReadonlyArray<string>).includes(code);

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** What to tell the respondent, in their language (`respondent` namespace, RULE.*). */
export function answerRuleMessage(field: StandardFormFieldDto, problem: AnswerRuleProblem, t: Translate, language: string = 'en'): string {
    const rules: IFormFieldValidation = field?.validations ?? {};
    switch (problem) {
        case 'TOO_SHORT':
            return t('RULE.TOO_SHORT', { count: rules.minLength });
        case 'TOO_LONG':
            if (field?.type === FieldTypes.SIGNATURE) return t('RULE.TOO_LONG', { count: SIGNATURE_NAME_MAX });
            if (field?.type === FieldTypes.ADDRESS) return t('RULE.ADDRESS_TOO_LONG');
            if (field?.type === FieldTypes.TAGS) return t('RULE.TAG_TOO_LONG', { count: tagLimits(field).length });
            return t('RULE.TOO_LONG', { count: rules.maxLength });
        case 'PATTERN': {
            const preset = presetForPattern(rules.regex);
            return preset ? t(`RULE.FORMAT_${preset.id.toUpperCase()}`, { example: preset.example }) : t('RULE.PATTERN');
        }
        case 'TOO_SMALL':
            if (field?.type === FieldTypes.TIME) return t('RULE.TOO_EARLY', { time: field.properties?.minTime });
            if (field?.type === FieldTypes.CURRENCY) return t('RULE.AMOUNT_TOO_SMALL', { min: formatAmount({ code: questionCurrencies(field)[0], amount: String(isSet(rules.minValue) ? rules.minValue : 0) }, language) });
            return t('RULE.TOO_SMALL', { min: rules.minValue });
        case 'TOO_LARGE':
            if (field?.type === FieldTypes.TIME) return t('RULE.TOO_LATE', { time: field.properties?.maxTime });
            if (field?.type === FieldTypes.CURRENCY) return t('RULE.AMOUNT_TOO_LARGE', { max: formatAmount({ code: questionCurrencies(field)[0], amount: String(rules.maxValue) }, language) });
            return t('RULE.TOO_LARGE', { max: rules.maxValue });
        case 'SIGNATURE_IMAGE':
            return t('RULE.SIGNATURE_IMAGE');
        case 'FORMAT':
            if (field?.type === FieldTypes.SIGNATURE) return t('RULE.FORMAT_SIGNATURE');
            if (field?.type === FieldTypes.TIME) return t('RULE.FORMAT_TIME');
            if (field?.type === FieldTypes.DAY) return t('RULE.FORMAT_DAY');
            if (field?.type === FieldTypes.DATE_RANGE) return t('RULE.FORMAT_RANGE');
            if (field?.type === FieldTypes.TAGS) return t('RULE.FORMAT_TAGS');
            if (field?.type === FieldTypes.ADDRESS) return t('RULE.FORMAT_ADDRESS');
            return t('RULE.FORMAT_AMOUNT');
        case 'REQUIRED':
            return field?.type === FieldTypes.ADDRESS ? t('RULE.ADDRESS_INCOMPLETE') : t('RULE.RANGE_INCOMPLETE');
        case 'COUNTRY':
            return t('RULE.COUNTRY', { countries: questionCountries(field).map((code) => countryName(code, language)).join(', ') });
        case 'RANGE_ORDER':
            return t('RULE.RANGE_ORDER');
        case 'DUPLICATE':
            return t('RULE.TAG_DUPLICATE');
        case 'CURRENCY':
            return t('RULE.CURRENCY', { currencies: questionCurrencies(field).join(', ') });
        case 'NOT_INTEGER':
            return t('RULE.NOT_INTEGER');
        case 'TOO_FEW_CHOICES':
            if (field?.type === FieldTypes.TAGS) return t('RULE.TOO_FEW_TAGS', { count: tagLimits(field).fewest });
            return t('RULE.TOO_FEW_CHOICES', { count: rules.minChoices });
        case 'TOO_MANY_CHOICES':
            if (field?.type === FieldTypes.TAGS) return t('RULE.TOO_MANY_TAGS', { count: tagLimits(field).most });
            return t('RULE.TOO_MANY_CHOICES', { count: rules.maxChoices });
    }
}

/** Plain-language summary of a field's active answer rules, for the builder. */
export function summarizeAnswerRules(field: StandardFormFieldDto): string[] {
    const rules: IFormFieldValidation = field?.validations ?? {};
    const lines: string[] = [];
    const range = (min: number | undefined, max: number | undefined, unitKey: 'characters' | 'options' | 'tags') => {
        const unit = i18n.t(`builder:RULES_SUMMARY.UNIT_${unitKey}`);
        if (isSet(min) && isSet(max)) return min === max ? i18n.t('builder:RULES_SUMMARY.EXACTLY', { min, unit }) : i18n.t('builder:RULES_SUMMARY.BETWEEN', { min, max, unit });
        if (isSet(min)) return i18n.t('builder:RULES_SUMMARY.AT_LEAST', { min, unit });
        if (isSet(max)) return i18n.t('builder:RULES_SUMMARY.AT_MOST', { max, unit });
        return null;
    };
    switch (answerRuleKind(field)) {
        case 'text': {
            const length = range(rules.minLength, rules.maxLength, 'characters');
            if (length) lines.push(i18n.t('builder:RULES_SUMMARY.ANSWER_IS', { range: length }));
            if (rules.regex) {
                const preset = presetForPattern(rules.regex);
                lines.push(preset ? i18n.t(`builder:RULES_SUMMARY.PRESET_${preset.id}`, { example: preset.example }) : i18n.t('builder:RULES_SUMMARY.CUSTOM'));
            }
            break;
        }
        case 'number': {
            if (isSet(rules.minValue) && isSet(rules.maxValue)) lines.push(i18n.t('builder:RULES_SUMMARY.NUMBER_RANGE', { min: rules.minValue, max: rules.maxValue }));
            else if (isSet(rules.minValue)) lines.push(i18n.t('builder:RULES_SUMMARY.NUMBER_MIN', { min: rules.minValue }));
            else if (isSet(rules.maxValue)) lines.push(i18n.t('builder:RULES_SUMMARY.NUMBER_MAX', { max: rules.maxValue }));
            if (rules.regex === INTEGER_PATTERN) lines.push(i18n.t('builder:RULES_SUMMARY.WHOLE'));
            else if (rules.regex) lines.push(i18n.t('builder:RULES_SUMMARY.CUSTOM'));
            break;
        }
        case 'choices': {
            const count = range(rules.minChoices, rules.maxChoices, 'options');
            if (count) lines.push(i18n.t('builder:RULES_SUMMARY.PICK', { range: count }));
            break;
        }
        case 'tags': {
            const limits = tagLimits(field);
            const count = range(limits.fewest || undefined, rules.maxChoices === undefined ? undefined : limits.most, 'tags');
            if (count) lines.push(i18n.t('builder:RULES_SUMMARY.ENTER', { range: count }));
            lines.push(i18n.t('builder:RULES_SUMMARY.TAG_LENGTH', { n: limits.length }));
            break;
        }
    }
    return lines;
}

/** Problems with the rules themselves (shown in the builder, next to the inputs). */
export function answerRuleConflicts(rules: IFormFieldValidation | undefined): string[] {
    const conflicts: string[] = [];
    if (!rules) return conflicts;
    if (isSet(rules.minLength) && isSet(rules.maxLength) && rules.minLength > rules.maxLength) conflicts.push(i18n.t('builder:RULES_SUMMARY.CONFLICT_LENGTH'));
    if (isSet(rules.minValue) && isSet(rules.maxValue) && rules.minValue > rules.maxValue) conflicts.push(i18n.t('builder:RULES_SUMMARY.CONFLICT_VALUE'));
    if (isSet(rules.minChoices) && isSet(rules.maxChoices) && rules.minChoices > rules.maxChoices) conflicts.push(i18n.t('builder:RULES_SUMMARY.CONFLICT_CHOICES'));
    if (rules.regex && rules.regex.length > PATTERN_MAX_LENGTH) conflicts.push(i18n.t('builder:RULES_SUMMARY.CONFLICT_PATTERN', { max: PATTERN_MAX_LENGTH }));
    return conflicts;
}
