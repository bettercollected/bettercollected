import React from 'react';

import { act, renderHook } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, LogicalOperator } from '@app/models/types/form-builder-shared';
import useFormFieldsAtom from './field-selectors';

/**
 * Each renderHook gets a fresh Jotai <Provider>, so module-level atoms are
 * isolated between tests.
 */
const setup = () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => <Provider>{children}</Provider>;
    return renderHook(() => useFormFieldsAtom(), { wrapper });
};

const q = (id: string, index: number, type: string = FieldTypes.SHORT_TEXT): StandardFormFieldDto => ({ id, index, type });

const twoPageForm = (): StandardFormFieldDto[] => [
    {
        id: 'slide-1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [q('q1', 0)],
            jumps: [{ operator: LogicalOperator.AND, conditions: [{ fieldId: 'q1', fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_EQUAL, value: 'skip' }], target: 'slide-2' }]
        }
    },
    { id: 'slide-2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [q('q2', 0)] } }
];

describe('initFormFields — undo baseline', () => {
    it('seeds fields and starts history with nothing to undo', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        expect(result.current.formFields).toHaveLength(2);
        expect(result.current.canUndo).toBe(false);
        expect(result.current.canRedo).toBe(false);
    });

    it('undo can never reach past the loaded form (data-loss guard)', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        act(() => result.current.deleteSlide(1));
        act(() => result.current.undo());
        expect(result.current.formFields).toHaveLength(2);
        expect(result.current.canUndo).toBe(false);
        // a further undo is a no-op, not a blank form
        act(() => result.current.undo());
        expect(result.current.formFields).toHaveLength(2);
    });
});

describe('undo / redo', () => {
    it('round-trips a structural change', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        act(() => result.current.deleteSlide(1));
        expect(result.current.formFields).toHaveLength(1);
        expect(result.current.canUndo).toBe(true);

        act(() => result.current.undo());
        expect(result.current.formFields).toHaveLength(2);
        expect(result.current.formFields[1].id).toBe('slide-2');
        expect(result.current.canRedo).toBe(true);

        act(() => result.current.redo());
        expect(result.current.formFields).toHaveLength(1);
        expect(result.current.canRedo).toBe(false);
    });

    it('a new change truncates the redo future', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        act(() => result.current.deleteSlide(1));
        act(() => result.current.undo());
        act(() => result.current.updateSlidePosition(0, { x: 10, y: 20 }));
        expect(result.current.canRedo).toBe(false);
    });

    it('identical consecutive commits are deduped (no wasted undo steps)', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        act(() => result.current.setFormFields([...result.current.formFields]));
        expect(result.current.canUndo).toBe(false);
    });

    it('undone state is a deep copy — later mutations cannot corrupt history', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        act(() => result.current.updateSlidePosition(0, { x: 1, y: 1 }));
        act(() => result.current.updateSlidePosition(0, { x: 2, y: 2 }));
        act(() => result.current.undo());
        expect(result.current.formFields[0].properties?.position).toEqual({ x: 1, y: 1 });
        act(() => result.current.undo());
        expect(result.current.formFields[0].properties?.position).toBeUndefined();
    });
});

describe('slide mutations', () => {
    it('addSlide appends and reindexes', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        act(() => result.current.addSlide({ id: 'slide-3', index: 2, type: FieldTypes.SLIDE, properties: { fields: [] } }, 2));
        expect(result.current.formFields).toHaveLength(3);
        expect(result.current.formFields.map((s) => s.index)).toEqual([0, 1, 2]);
    });

    it('deleteSlide removes, reindexes, and prunes conditions referencing its fields', () => {
        const { result } = setup();
        // slide-2 has a jump conditioned on q1 (slide-1's field); deleting slide-1 must prune it
        const form: StandardFormFieldDto[] = [
            { id: 'slide-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [q('q1', 0)] } },
            {
                id: 'slide-2',
                index: 1,
                type: FieldTypes.SLIDE,
                properties: {
                    fields: [q('q2', 0)],
                    jumps: [{ operator: LogicalOperator.AND, conditions: [{ fieldId: 'q1', fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_NOT_EMPTY, value: '' }], target: 'slide-1' }]
                }
            }
        ];
        act(() => result.current.initFormFields(form));
        act(() => result.current.deleteSlide(0));
        expect(result.current.formFields).toHaveLength(1);
        expect(result.current.formFields[0].index).toBe(0);
        // the jump conditioned on the deleted q1 is swept
        expect(result.current.formFields[0].properties?.jumps).toBeUndefined();
    });

    it('duplicateSlide deep-copies with fresh ids and no inherited canvas position', () => {
        const { result } = setup();
        const form = twoPageForm();
        form[0].properties!.position = { x: 100, y: 200 };
        act(() => result.current.initFormFields(form));
        let newId: string | undefined;
        act(() => {
            newId = result.current.duplicateSlide(0);
        });
        expect(result.current.formFields).toHaveLength(3);
        const copy = result.current.formFields[1];
        expect(copy.id).toBe(newId);
        expect(copy.id).not.toBe('slide-1');
        expect(copy.properties?.fields?.[0].id).not.toBe('q1');
        expect(copy.properties?.position).toBeUndefined();
        expect(result.current.formFields.map((s) => s.index)).toEqual([0, 1, 2]);
        // the original keeps its identity
        expect(result.current.formFields[0].id).toBe('slide-1');
    });
});

describe('field mutations', () => {
    it('deleteField removes, reindexes, and prunes logic referencing it', () => {
        const { result } = setup();
        const form: StandardFormFieldDto[] = [
            {
                id: 'slide-1',
                index: 0,
                type: FieldTypes.SLIDE,
                properties: {
                    fields: [
                        q('q1', 0),
                        { ...q('q2', 1), properties: { logic: { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'q1', fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_NOT_EMPTY, value: '' }] } } }
                    ]
                }
            }
        ];
        act(() => result.current.initFormFields(form));
        act(() => result.current.deleteField(0, 0)); // delete q1
        const fields = result.current.formFields[0].properties!.fields!;
        expect(fields).toHaveLength(1);
        expect(fields[0].id).toBe('q2');
        expect(fields[0].index).toBe(0);
        // q2's visibility rule referenced the deleted q1 → swept
        expect(fields[0].properties?.logic).toBeUndefined();
    });

    it('updateFieldConditionalLogic sets and clears a rule (fieldIndex first, slideIndex second)', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        const rule = { action: 'SHOW' as const, operator: LogicalOperator.AND, conditions: [{ fieldId: 'q1', fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_EQUAL, value: 'x' }] };
        act(() => result.current.updateFieldConditionalLogic(0, 1, rule));
        expect(result.current.formFields[1].properties?.fields?.[0].properties?.logic).toEqual(rule);
        act(() => result.current.updateFieldConditionalLogic(0, 1, undefined));
        expect(result.current.formFields[1].properties?.fields?.[0].properties?.logic).toBeUndefined();
    });
});

describe('flow-view mutations', () => {
    it('updateSlideJumps sets and clears jump rules', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        const jumps = [{ operator: LogicalOperator.AND, conditions: [{ fieldId: 'q1', fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_EQUAL, value: 'y' }], target: '__SUBMIT__' }];
        act(() => result.current.updateSlideJumps(1, jumps));
        expect(result.current.formFields[1].properties?.jumps).toEqual(jumps);
        act(() => result.current.updateSlideJumps(1, undefined));
        expect(result.current.formFields[1].properties?.jumps).toBeUndefined();
    });

    it('updateSlidePosition and clearSlidePositions manage the canvas layout', () => {
        const { result } = setup();
        act(() => result.current.initFormFields(twoPageForm()));
        act(() => result.current.updateSlidePosition(0, { x: 42, y: 7 }));
        act(() => result.current.updateSlidePosition(1, { x: 1, y: 2 }));
        expect(result.current.formFields[0].properties?.position).toEqual({ x: 42, y: 7 });
        act(() => result.current.clearSlidePositions());
        expect(result.current.formFields[0].properties?.position).toBeUndefined();
        expect(result.current.formFields[1].properties?.position).toBeUndefined();
    });
});
