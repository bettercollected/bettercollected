import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison } from '@app/models/types/form-builder-shared';
import { buildSourceFields, comparisonsForField, fieldText, isConditionComplete, needsValue, newConditionFor, pageLabel } from './condition-editor-shared';

const field = (id: string, index: number, opts: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index, type: FieldTypes.SHORT_TEXT, ...opts });

const slide = (id: string, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;

const tiptapTitle = (text: string) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });

describe('fieldText — labels always match what the canvas shows', () => {
    it('uses a plain-string title', () => {
        expect(fieldText(field('f', 0, { title: 'Your name?' }))).toBe('Your name?');
    });

    it('extracts text from a Tiptap JSON title', () => {
        expect(fieldText(field('f', 0, { title: tiptapTitle('Rich title') as any }))).toBe('Rich title');
    });

    it('falls back to the type placeholder for untitled questions (canvas parity)', () => {
        // The canvas shows "Enter Question" for an untitled short-text — the picker must match.
        expect(fieldText(field('f', 0, { type: FieldTypes.SHORT_TEXT }))).toBe('Enter Question');
    });

    it('handles missing fields', () => {
        expect(fieldText(undefined)).toBe('');
    });
});

describe('pageLabel — stable, content-derived page names', () => {
    it('includes the first question text', () => {
        expect(pageLabel(slide('s', [field('f', 0, { title: 'Contact info' })]), 0)).toBe('Page 1 · Contact info');
    });

    it('falls back to the bare page number for empty pages', () => {
        expect(pageLabel(slide('s', []), 2)).toBe('Page 3');
    });
});

describe('buildSourceFields', () => {
    const form = [slide('s1', [field('a', 0, { title: 'A' }), field('b', 1, { title: 'B' })]), slide('s2', [field('c', 0, { title: 'C' })])];

    it('applies the predicate and labels with page context on multi-page forms', () => {
        const sources = buildSourceFields(form, (_s, sIdx) => sIdx === 0);
        expect(sources.map((s) => s.field.id)).toEqual(['a', 'b']);
        expect(sources[0].label).toBe('Page 1 · A');
    });

    it('omits the page prefix on single-page forms', () => {
        const sources = buildSourceFields([form[0]], () => true);
        expect(sources[0].label).toBe('A');
    });
});

describe('comparisonsForField — comparators adapt to the source type', () => {
    it('Yes/No only offers equality', () => {
        const c = comparisonsForField(field('f', 0, { type: FieldTypes.YES_NO }));
        expect(c).toEqual([Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL]);
    });

    it('numeric types offer ordering comparators', () => {
        const c = comparisonsForField(field('f', 0, { type: FieldTypes.NUMBER }));
        expect(c).toContain(Comparison.GREATER_THAN);
        expect(c).toContain(Comparison.LESS_THAN_EQUAL);
        expect(c).not.toContain(Comparison.CONTAINS);
    });

    it('multi-select choice fields use membership comparators', () => {
        const single = comparisonsForField(field('f', 0, { type: FieldTypes.MULTIPLE_CHOICE }));
        expect(single).toContain(Comparison.IS_EQUAL);
        const multi = comparisonsForField(field('f', 0, { type: FieldTypes.MULTIPLE_CHOICE, properties: { allowMultipleSelection: true } }));
        expect(multi).toContain(Comparison.CONTAINS);
        expect(multi).not.toContain(Comparison.IS_EQUAL);
    });

    it('text types offer the full string set', () => {
        const c = comparisonsForField(field('f', 0));
        expect(c).toEqual(expect.arrayContaining([Comparison.CONTAINS, Comparison.STARTS_WITH, Comparison.ENDS_WITH, Comparison.IS_EMPTY]));
    });
});

describe('rule completeness', () => {
    it('needsValue is false only for the emptiness checks', () => {
        expect(needsValue(Comparison.IS_EMPTY)).toBe(false);
        expect(needsValue(Comparison.IS_NOT_EMPTY)).toBe(false);
        expect(needsValue(Comparison.IS_EQUAL)).toBe(true);
    });

    it('isConditionComplete requires field, comparison, and (when needed) a value', () => {
        expect(isConditionComplete({ fieldId: 'f', fieldType: 't', comparison: Comparison.IS_EQUAL, value: 'x' })).toBe(true);
        expect(isConditionComplete({ fieldId: 'f', fieldType: 't', comparison: Comparison.IS_EQUAL, value: '' })).toBe(false);
        expect(isConditionComplete({ fieldId: 'f', fieldType: 't', comparison: Comparison.IS_EMPTY, value: '' })).toBe(true);
        expect(isConditionComplete({ fieldId: '', fieldType: 't', comparison: Comparison.IS_EQUAL, value: 'x' })).toBe(false);
        expect(isConditionComplete(undefined)).toBe(false);
    });

    it('newConditionFor seeds from the first source (or empty when none)', () => {
        const sources = buildSourceFields([slide('s1', [field('a', 0, { title: 'A' })])], () => true);
        expect(newConditionFor(sources)).toMatchObject({ fieldId: 'a', comparison: Comparison.IS_EQUAL, value: '' });
        expect(newConditionFor([])).toMatchObject({ fieldId: '', comparison: Comparison.IS_EQUAL });
    });
});
