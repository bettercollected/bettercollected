import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { DateRule } from '@app/models/types/form-builder-shared';
import { getInputFieldsById } from '@app/utils/answer-piping';
import {
    formatIsoDate,
    getDateRuleError,
    getDateRuleSources,
    getDisabledDayMatcher,
    isDateRuleViolated,
    isIsoDate,
    isoToLocalDate,
    pruneOrphanedDateRules,
    remapDateRules,
    toIsoDate,
    validateDateRulesInSlide,
    wouldCreateDateRuleCycle
} from '@app/utils/date-rules';
import { remapGroupChildIds } from '@app/utils/repeating-groups';

const date = (id: string, title: string, dateRules?: DateRule[], extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({
    id,
    index: 0,
    type: FieldTypes.DATE,
    title,
    ...extra,
    properties: { ...(extra.properties ?? {}), ...(dateRules ? { dateRules } : {}) }
});
const slide = (id: string, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields } });
const group = (id: string, children: StandardFormFieldDto[]): StandardFormFieldDto => ({
    id,
    index: 0,
    type: FieldTypes.GROUP,
    title: 'Stays',
    properties: { repeat: { minItems: 1, maxItems: 3, itemLabel: 'Stay' }, fields: children }
});
const after = (fieldId: string, comparison: DateRule['comparison'] = 'after'): DateRule => ({ comparison, target: 'field', fieldId });
const day = (value: string) => ({ type: 'date', date: value });

const start = date('start', 'Start date');
const end = date('end', 'End date', [after('start')]);
const slides = () => [slide('s1', [start, end])];
const context = (answers: Record<string, any>, forms = slides()) => ({ answers, fieldsById: getInputFieldsById(forms), today: '2026-10-02' });

describe('calendar dates', () => {
    it('accepts only real YYYY-MM-DD dates', () => {
        expect(isIsoDate('2026-03-12')).toBe(true);
        expect(isIsoDate('2026-02-30')).toBe(false);
        expect(isIsoDate('12/03/2026')).toBe(false);
        expect(isIsoDate(undefined)).toBe(false);
    });

    it('round-trips local days without a time-zone shift', () => {
        const local = isoToLocalDate('2026-03-12')!;
        expect([local.getFullYear(), local.getMonth(), local.getDate()]).toEqual([2026, 2, 12]);
        expect(toIsoDate(local)).toBe('2026-03-12');
        // Late evening is still the same calendar day.
        expect(toIsoDate(new Date(2026, 2, 12, 23, 59))).toBe('2026-03-12');
    });

    it('formats like the backend', () => {
        expect(formatIsoDate('2026-03-02')).toBe('2 Mar 2026');
    });

    it('compares calendar days', () => {
        expect(isDateRuleViolated('2026-03-12', 'after', '2026-03-12')).toBe(true);
        expect(isDateRuleViolated('2026-03-12', 'on_or_after', '2026-03-12')).toBe(false);
        expect(isDateRuleViolated('2026-03-11', 'before', '2026-03-12')).toBe(false);
        expect(isDateRuleViolated('2026-03-13', 'on_or_before', '2026-03-12')).toBe(true);
    });
});

describe('rule evaluation', () => {
    it('explains a broken rule with the other question and its date', () => {
        expect(getDateRuleError(end, context({ start: day('2026-03-12'), end: day('2026-03-12') }))).toBe('Must be after Start date (12 Mar 2026).');
        expect(getDateRuleError(end, context({ start: day('2026-03-12'), end: day('2026-03-13') }))).toBeUndefined();
    });

    it('names the other question by its label when it has one', () => {
        const labelled = [slide('s1', [date('start', 'When do you leave?', undefined, { properties: { label: 'Start date' } }), end])];
        expect(getDateRuleError(end, context({ start: day('2026-03-12'), end: day('2026-03-01') }, labelled))).toBe('Must be after Start date (12 Mar 2026).');
    });

    it('does not apply while the other question is unanswered', () => {
        expect(getDateRuleError(end, context({ end: day('2000-01-01') }))).toBeUndefined();
    });

    it('does not apply while the other question is hidden by logic', () => {
        const hiddenStart = date('start', 'Start date', undefined, {
            properties: { logic: { action: 'SHOW', operator: 'AND' as any, conditions: [{ fieldId: 'trip', fieldType: FieldTypes.YES_NO, comparison: 'IS_EQUAL' as any, value: 'Yes' }] } }
        });
        const forms = [slide('s1', [{ id: 'trip', index: 0, type: FieldTypes.YES_NO, title: 'Trip?' }, hiddenStart, end])];
        const answers = { trip: { boolean: false }, start: day('2026-03-12'), end: day('2026-03-01') };
        expect(getDateRuleError(end, context(answers, forms))).toBeUndefined();
        expect(getDateRuleError(end, context({ ...answers, trip: { boolean: true } }, forms))).toBe('Must be after Start date (12 Mar 2026).');
    });

    it('checks fixed dates and today', () => {
        const field = date('d', 'Date', [
            { comparison: 'on_or_after', target: 'date', date: '2026-01-01' },
            { comparison: 'on_or_before', target: 'today' }
        ]);
        const forms = [slide('s1', [field])];
        expect(getDateRuleError(field, context({ d: day('2025-12-31') }, forms))).toBe('Must be on or after 1 Jan 2026.');
        expect(getDateRuleError(field, context({ d: day('2026-10-03') }, forms))).toBe('Must be on or before today (2 Oct 2026).');
        expect(getDateRuleError(field, context({ d: day('2026-10-02') }, forms))).toBeUndefined();
        expect(getDateRuleError(field, context({ d: day('soon') }, forms))).toBe('Please pick a valid date.');
    });

    it('disables the days the rules rule out', () => {
        const matcher = getDisabledDayMatcher(end, context({ start: day('2026-03-12') }))!;
        expect(matcher(new Date(2026, 2, 12))).toBe(true);
        expect(matcher(new Date(2026, 2, 13))).toBe(false);
        expect(getDisabledDayMatcher(end, context({}))).toBeUndefined();
    });

    it('validates a page, top level and per group item', () => {
        const stays = group('g', [date('in', 'Check-in'), date('out', 'Check-out', [after('in')])]);
        const forms = [slide('s1', [start, end, stays])];
        const answers = {
            start: day('2026-03-12'),
            end: day('2026-03-11'),
            g: {
                type: 'group',
                items: [
                    { in: day('2026-03-01'), out: day('2026-03-02') },
                    { in: day('2026-03-05'), out: day('2026-03-05') }
                ]
            }
        };
        expect(validateDateRulesInSlide(forms[0].properties!.fields, answers, getInputFieldsById(forms), '2026-10-02')).toEqual({ end: ['DATE_RULE'], 'out::1': ['DATE_RULE'] });
    });
});

describe('builder helpers', () => {
    it('offers earlier date questions of the same scope only', () => {
        const stays = group('g', [date('in', 'Check-in'), date('out', 'Check-out')]);
        const forms = [slide('s1', [start, { id: 'name', index: 1, type: FieldTypes.SHORT_TEXT, title: 'Name' }, date('internal', 'Office date', undefined, { internal: true }), end, stays])];
        expect(getDateRuleSources(forms, 'end').map((s) => s.id)).toEqual(['start']);
        expect(getDateRuleSources(forms, 'start')).toEqual([]);
        expect(getDateRuleSources(forms, 'out').map((s) => s.id)).toEqual(['in']);
    });

    it('never offers a question that would close a circle', () => {
        // "start" was moved below "end", which already uses it.
        const forms = [slide('s1', [end, start])];
        expect(wouldCreateDateRuleCycle(forms, 'start', 'end')).toBe(true);
        expect(getDateRuleSources(forms, 'start')).toEqual([]);
    });

    it('prunes rules on removed, internal, non-date or cross-scope questions', () => {
        const stays = group('g', [date('in', 'Check-in'), date('out', 'Check-out', [after('start')])]);
        const forms = [
            slide('s1', [
                date('end', 'End', [after('gone'), after('internal'), after('name'), { comparison: 'after', target: 'today' }]),
                date('internal', 'X', undefined, { internal: true }),
                { id: 'name', index: 0, type: FieldTypes.SHORT_TEXT },
                start,
                stays
            ])
        ];
        pruneOrphanedDateRules(forms);
        expect(forms[0].properties!.fields![0].properties!.dateRules).toEqual([{ comparison: 'after', target: 'today' }]);
        expect(stays.properties!.fields![1].properties!.dateRules).toBeUndefined();
    });

    it('remaps references of copied questions', () => {
        const copy = [date('start2', 'Start'), date('end2', 'End', [after('start'), after('elsewhere')])];
        remapDateRules(copy, { start: 'start2' });
        expect(copy[1].properties!.dateRules!.map((r) => r.fieldId)).toEqual(['start2', 'elsewhere']);

        const stays = group('g', [date('in', 'Check-in'), date('out', 'Check-out', [after('in')])]);
        let next = 0;
        remapGroupChildIds(stays, () => `new-${next++}`);
        expect(stays.properties!.fields!.map((c) => c.id)).toEqual(['new-0', 'new-1']);
        expect(stays.properties!.fields![1].properties!.dateRules![0].fieldId).toBe('new-0');
    });
});

describe('naming the other date question', () => {
    it('uses the label, then the title text, then a neutral phrase', async () => {
        const { dateFieldName, dateQuestionTitle } = await import('@app/utils/date-rules');
        const untitled = { id: 'd1', type: 'date', properties: {} } as any;
        expect(dateFieldName(untitled)).toBe('the other date');
        expect(dateQuestionTitle(untitled)).toBe('Select a date');
        const rich = { id: 'd2', type: 'date', title: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Start date' }] }] }, properties: {} } as any;
        expect(dateFieldName(rich)).toBe('Start date');
        expect(dateFieldName({ ...rich, properties: { label: 'Arrival' } })).toBe('Arrival');
    });
});
