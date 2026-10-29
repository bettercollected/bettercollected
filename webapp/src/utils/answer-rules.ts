import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { IFormFieldValidation } from '@app/models/types/form-builder-shared';
import type { LogicSources } from '@app/utils/conditional-logic';
import { PatternHazard, patternHazard } from '@app/utils/pattern-safety';
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
 *
 * An empty answer is never checked here: whether one is needed is what
 * Required says.
 */

export type AnswerRuleKind = 'text' | 'number' | 'choices';

export type AnswerRuleProblem = 'TOO_SHORT' | 'TOO_LONG' | 'PATTERN' | 'TOO_SMALL' | 'TOO_LARGE' | 'NOT_INTEGER' | 'TOO_FEW_CHOICES' | 'TOO_MANY_CHOICES';

export const ANSWER_RULE_PROBLEMS: ReadonlyArray<AnswerRuleProblem> = ['TOO_SHORT', 'TOO_LONG', 'PATTERN', 'TOO_SMALL', 'TOO_LARGE', 'NOT_INTEGER', 'TOO_FEW_CHOICES', 'TOO_MANY_CHOICES'];

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

/** The pattern as a RegExp (compiled, never run), or null when it does not compile. Unicode first (for \p{L}), then plain. */
function compileRaw(pattern: string): RegExp | null {
    try {
        return new RegExp(pattern, 'u');
    } catch {
        try {
            return new RegExp(pattern);
        } catch {
            return null;
        }
    }
}

/**
 * The pattern as a RegExp to test answers with, or null when it must not be
 * tested here: it does not compile, or its shape can take this backtracking
 * engine exponential time (`^(a+)+$`, utils/pattern-safety.ts). The server
 * checks such a pattern with RE2 (linear time) when the answer is submitted
 * and answers 422, which the form shows next to the question.
 */
export function compilePattern(pattern: string | undefined | null): RegExp | null {
    if (!pattern) return null;
    const compiled = compileRaw(pattern);
    if (!compiled || patternHazard(pattern)) return null;
    return compiled;
}

/**
 * The longest answer (in UTF-16 units) this browser tests against a pattern.
 * The structural check (utils/pattern-safety.ts) bounds the work of a pattern
 * for answers up to about this long (WORK_UNBOUNDED) but cannot prove no
 * pattern is super-linear, so a longer answer is left to the server, which
 * matches with RE2 (linear time) up to PATTERN_INPUT_MAX_LENGTH, 10,000
 * characters, when the answer is submitted.
 */
export const PATTERN_TEST_MAX_LENGTH = 1000;

/**
 * Whether the answer breaks the pattern, as far as this browser can tell:
 * false when the pattern must not be tested here (does not compile, unsafe
 * shape) or the answer is longer than PATTERN_TEST_MAX_LENGTH.
 */
export function patternBreaks(pattern: string | undefined | null, text: string): boolean {
    if (text.length > PATTERN_TEST_MAX_LENGTH) return false;
    const compiled = compilePattern(pattern);
    return !!compiled && !compiled.test(text);
}

/** What is wrong with a pattern the builder is given: it does not compile, or its shape is a hazard. null when it is fine. */
export function patternProblem(pattern: string | undefined | null): 'invalid' | PatternHazard | null {
    if (!pattern) return null;
    const hazard = patternHazard(pattern);
    if (!compileRaw(pattern)) {
        // the server refuses a hazard even where this browser cannot compile the pattern ((?i), (?P<x>...))
        return hazard && hazard !== 'unparseable' && hazard !== 'too_complex' ? hazard : 'invalid';
    }
    return hazard;
}

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

function answerChoiceCount(answer: any): number | undefined {
    const choices = answer?.choices;
    if (!choices) return undefined;
    const count = (choices.values?.length ?? 0) + (typeof choices.other === 'string' && choices.other.trim() ? 1 : 0);
    return count > 0 ? count : undefined;
}

/** The rules an answer breaks (empty when it keeps them all, or is empty). */
export function checkAnswerRules(field: StandardFormFieldDto, answer: any): AnswerRuleProblem[] {
    const rules: IFormFieldValidation = field?.validations ?? {};
    const problems: AnswerRuleProblem[] = [];
    switch (answerRuleKind(field)) {
        case 'text': {
            const text = answerText(answer);
            if (text === undefined) break;
            // Count characters as people do (an emoji is one).
            const length = Array.from(text).length;
            if (isSet(rules.minLength) && length < rules.minLength) problems.push('TOO_SHORT');
            if (isSet(rules.maxLength) && length > rules.maxLength) problems.push('TOO_LONG');
            if (patternBreaks(rules.regex, text.trim())) problems.push('PATTERN');
            break;
        }
        case 'number': {
            const number = answerNumber(answer);
            if (!number) break;
            if (isSet(rules.minValue) && number.value < rules.minValue) problems.push('TOO_SMALL');
            if (isSet(rules.maxValue) && number.value > rules.maxValue) problems.push('TOO_LARGE');
            if (rules.regex && patternBreaks(rules.regex, number.typed)) problems.push(rules.regex === INTEGER_PATTERN ? 'NOT_INTEGER' : 'PATTERN');
            break;
        }
        case 'choices': {
            const count = answerChoiceCount(answer);
            if (count === undefined) break;
            if (isSet(rules.minChoices) && count < rules.minChoices) problems.push('TOO_FEW_CHOICES');
            if (isSet(rules.maxChoices) && count > rules.maxChoices) problems.push('TOO_MANY_CHOICES');
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
export function validateAnswerRulesInSlide(fields: ReadonlyArray<StandardFormFieldDto> | undefined, answers: Record<string, any>, sources?: LogicSources): Record<string, AnswerRuleProblem[]> {
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
        const problems = checkAnswerRules(field, answers[field.id]);
        if (problems.length) invalid[field.id] = problems;
    });
    return invalid;
}

export const isAnswerRuleProblem = (code: unknown): code is AnswerRuleProblem => typeof code === 'string' && (ANSWER_RULE_PROBLEMS as ReadonlyArray<string>).includes(code);

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** What to tell the respondent, in their language (`respondent` namespace, RULE.*). */
export function answerRuleMessage(field: StandardFormFieldDto, problem: AnswerRuleProblem, t: Translate): string {
    const rules: IFormFieldValidation = field?.validations ?? {};
    switch (problem) {
        case 'TOO_SHORT':
            return t('RULE.TOO_SHORT', { count: rules.minLength });
        case 'TOO_LONG':
            return t('RULE.TOO_LONG', { count: rules.maxLength });
        case 'PATTERN': {
            const preset = presetForPattern(rules.regex);
            return preset ? t(`RULE.FORMAT_${preset.id.toUpperCase()}`, { example: preset.example }) : t('RULE.PATTERN');
        }
        case 'TOO_SMALL':
            return t('RULE.TOO_SMALL', { min: rules.minValue });
        case 'TOO_LARGE':
            return t('RULE.TOO_LARGE', { max: rules.maxValue });
        case 'NOT_INTEGER':
            return t('RULE.NOT_INTEGER');
        case 'TOO_FEW_CHOICES':
            return t('RULE.TOO_FEW_CHOICES', { count: rules.minChoices });
        case 'TOO_MANY_CHOICES':
            return t('RULE.TOO_MANY_CHOICES', { count: rules.maxChoices });
    }
}

/** Plain-language summary of a field's active answer rules, for the builder. */
export function summarizeAnswerRules(field: StandardFormFieldDto): string[] {
    const rules: IFormFieldValidation = field?.validations ?? {};
    const lines: string[] = [];
    const range = (min: number | undefined, max: number | undefined, unit: string) => {
        if (isSet(min) && isSet(max)) return min === max ? `exactly ${min} ${unit}` : `between ${min} and ${max} ${unit}`;
        if (isSet(min)) return `at least ${min} ${unit}`;
        if (isSet(max)) return `at most ${max} ${unit}`;
        return null;
    };
    switch (answerRuleKind(field)) {
        case 'text': {
            const length = range(rules.minLength, rules.maxLength, 'characters');
            if (length) lines.push(`Answer is ${length}.`);
            if (rules.regex) {
                const preset = presetForPattern(rules.regex);
                lines.push(preset ? `Answer must be ${preset.summary}, e.g. ${preset.example}.` : 'Answer must match a custom pattern.');
            }
            break;
        }
        case 'number': {
            if (isSet(rules.minValue) && isSet(rules.maxValue)) lines.push(`Number from ${rules.minValue} to ${rules.maxValue}.`);
            else if (isSet(rules.minValue)) lines.push(`Number of at least ${rules.minValue}.`);
            else if (isSet(rules.maxValue)) lines.push(`Number of at most ${rules.maxValue}.`);
            if (rules.regex === INTEGER_PATTERN) lines.push('Whole numbers only.');
            else if (rules.regex) lines.push('Answer must match a custom pattern.');
            break;
        }
        case 'choices': {
            const count = range(rules.minChoices, rules.maxChoices, 'options');
            if (count) lines.push(`Pick ${count}.`);
            break;
        }
    }
    return lines;
}

/** Problems with the rules themselves (shown in the builder, next to the inputs). */
export function answerRuleConflicts(rules: IFormFieldValidation | undefined): string[] {
    const conflicts: string[] = [];
    if (!rules) return conflicts;
    if (isSet(rules.minLength) && isSet(rules.maxLength) && rules.minLength > rules.maxLength) conflicts.push('The minimum length is more than the maximum.');
    if (isSet(rules.minValue) && isSet(rules.maxValue) && rules.minValue > rules.maxValue) conflicts.push('The lowest value is more than the highest.');
    if (isSet(rules.minChoices) && isSet(rules.maxChoices) && rules.minChoices > rules.maxChoices) conflicts.push('The minimum number of options is more than the maximum.');
    // a pattern that is a hazard is explained next to the pattern box (translated)
    if (rules.regex && patternProblem(rules.regex) === 'invalid') conflicts.push('The pattern is not a valid regular expression, so it is not checked.');
    else if (rules.regex && rules.regex.length > PATTERN_MAX_LENGTH) conflicts.push(`The pattern is longer than ${PATTERN_MAX_LENGTH} characters. Shorten it.`);
    return conflicts;
}
