import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { buildSourceFields } from '@app/views/molecules/form-builder/condition-editor-shared';

import { getInputFieldsById, pruneOrphanedPipes } from './answer-piping';
import { pruneOrphanedConditions } from './conditional-logic';
import { getFieldsFromV2Form } from './form-utils';
import { buildInternalAnswer, canBeInternal, conflictingInternalFields, getInternalFields, internalAnswerChanged, internalAnswerToInput, stripInternalFields } from './internal-fields';

const field = (id: string, index: number, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index, type: FieldTypes.SHORT_TEXT, title: id, ...extra }) as StandardFormFieldDto;

const slide = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;

const form = (): Pick<StandardFormDto, 'fields' | 'builderVersion'> => ({
    builderVersion: 'v2',
    fields: [slide('page-1', 0, [field('name', 0), field('reference', 1, { internal: true })]), slide('page-2', 1, [field('status', 0, { internal: true, type: FieldTypes.MULTIPLE_CHOICE })]), slide('page-3', 2, [])]
});

describe('stripInternalFields', () => {
    it('removes internal fields and pages left empty by them, keeping originally-empty pages', () => {
        const original = form();
        const stripped = stripInternalFields(original);
        expect(stripped.fields.map((s) => s.id)).toEqual(['page-1', 'page-3']);
        expect(stripped.fields[0].properties?.fields?.map((f) => f.id)).toEqual(['name']);
        // never mutates the input
        expect(original.fields[0].properties?.fields).toHaveLength(2);
    });

    it('returns the same object when there is nothing internal', () => {
        const plain = { fields: [slide('p', 0, [field('a', 0)])] };
        expect(stripInternalFields(plain)).toBe(plain);
    });
});

describe('getInternalFields', () => {
    it('lists internal questions in order', () => {
        expect(getInternalFields(form()).map((f) => f.id)).toEqual(['reference', 'status']);
    });
});

describe('respondent-facing helpers ignore internal fields', () => {
    it('are not response columns, logic sources, pipe targets or prefill targets', () => {
        const f = form() as StandardFormDto;
        expect(getFieldsFromV2Form(f).map((x) => x.id)).toEqual(['name']);
        expect(buildSourceFields(f.fields, () => true).map((s) => s.field.id)).toEqual(['name']);
        expect(Object.keys(getInputFieldsById(f.fields))).toEqual(['name']);
    });

    it('prunes conditions and pipes that point at an internal field', () => {
        const slides = form().fields;
        slides[0].properties!.jumps = [{ operator: 'AND', target: 'page-3', conditions: [{ fieldId: 'reference', fieldType: FieldTypes.SHORT_TEXT, comparison: 'is_not_empty' }] }] as any;
        slides[0].properties!.fields![0].properties = { logic: { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'status', fieldType: FieldTypes.MULTIPLE_CHOICE, comparison: 'is_empty' }] } } as any;
        slides[0].properties!.fields![0].title = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'reference' } }] }] } as any;

        pruneOrphanedConditions(slides);
        pruneOrphanedPipes(slides);

        expect(slides[0].properties?.jumps).toBeUndefined();
        expect(slides[0].properties?.fields?.[0].properties?.logic).toBeUndefined();
        expect(JSON.stringify(slides[0].properties?.fields?.[0].title)).not.toContain('reference');
    });
});

describe('internal answer editing', () => {
    const choiceField = field('status', 0, { type: FieldTypes.MULTIPLE_CHOICE, properties: { choices: [{ id: 'c1', value: 'Open' }] } });

    it('builds answers in the same slots the responder uses', () => {
        expect(buildInternalAnswer(field('r', 0), 'REF-1')).toEqual({ field: { id: 'r' }, type: 'text', text: 'REF-1' });
        expect(buildInternalAnswer(field('n', 0, { type: FieldTypes.NUMBER }), '42')).toMatchObject({ number: 42 });
        expect(buildInternalAnswer(field('d', 0, { type: FieldTypes.DATE }), '2026-01-31')).toMatchObject({ date: '2026-01-31' });
        expect(buildInternalAnswer(field('y', 0, { type: FieldTypes.YES_NO }), false)).toMatchObject({ boolean: false });
        expect(buildInternalAnswer(choiceField, 'c1')).toMatchObject({ choice: { value: 'c1' } });
        expect(buildInternalAnswer(choiceField, ['c1'])).toMatchObject({ choices: { values: ['c1'] } });
    });

    it('treats blank values as clearing and round-trips stored answers', () => {
        expect(buildInternalAnswer(field('r', 0), '')).toBeNull();
        expect(buildInternalAnswer(field('n', 0, { type: FieldTypes.NUMBER }), 'abc')).toBeNull();
        const stored = buildInternalAnswer(choiceField, 'c1') as any;
        expect(internalAnswerToInput(choiceField, stored)).toBe('c1');
        expect(internalAnswerChanged(choiceField, stored, 'c1')).toBe(false);
        expect(internalAnswerChanged(choiceField, stored, '')).toBe(true);
    });

    it('finds which of my changed fields someone else changed meanwhile', () => {
        const ref = field('ref', 0);
        const note = field('note', 1);
        const baseline = { ref: buildInternalAnswer(ref, 'A') as any };
        const latest = { ref: buildInternalAnswer(ref, 'A') as any, note: buildInternalAnswer(note, 'theirs') as any };
        // they changed `note`, I changed `ref`: no clash, retry is safe
        expect(conflictingInternalFields([ref, note], ['ref'], baseline, latest)).toEqual([]);
        // we both changed `note`
        expect(conflictingInternalFields([ref, note], ['note'], baseline, latest).map((f) => f.id)).toEqual(['note']);
    });

    it('only allows simple field types to be internal', () => {
        expect(canBeInternal(field('a', 0))).toBe(true);
        expect(canBeInternal(field('b', 0, { type: FieldTypes.FILE_UPLOAD }))).toBe(false);
        expect(canBeInternal(field('c', 0, { type: FieldTypes.MATRIX }))).toBe(false);
    });
});
