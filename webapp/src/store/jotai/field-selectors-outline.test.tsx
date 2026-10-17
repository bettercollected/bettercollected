import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider } from 'jotai';
import { beforeEach, describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';

import useFormFieldsAtom from './field-selectors';

const q = (id: string, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title: id, ...extra }) as StandardFormFieldDto;
const cond = (fieldId: string) => ({ fieldId, fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_NOT_EMPTY, value: '' });
const pipeTitle = (fieldId: string) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi ' }, { type: 'answerPipe', attrs: { kind: 'field', pipeKey: fieldId } }] }] });

const page = (id: string, fields: StandardFormFieldDto[], extra: Record<string, any> = {}): StandardFormFieldDto =>
    ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields: fields.map((f, index) => ({ ...f, index })), ...extra } }) as StandardFormFieldDto;

// p1: name, email · p2: city (shown when name answered), greeting (pipes name)
// p3: notes · p2 jumps on name to p3; p3 jumps on notes to submit.
const form = (): StandardFormFieldDto[] =>
    [
        page('p1', [q('name'), q('email')]),
        page('p2', [q('city', { properties: { logic: { action: 'SHOW', operator: LogicalOperator.AND, conditions: [cond('name')] } } }), q('greeting', { title: pipeTitle('name') as any })], {
            jumps: [{ operator: LogicalOperator.AND, conditions: [cond('name')], target: 'p3' }]
        }),
        page('p3', [q('notes')], { jumps: [{ operator: LogicalOperator.AND, conditions: [cond('notes')], target: JUMP_TARGET_SUBMIT }] })
    ].map((slide, index) => ({ ...slide, index }));

let builder: ReturnType<typeof useFormFieldsAtom>;
let active: { slide: ReturnType<typeof useActiveSlideComponent>; field: ReturnType<typeof useActiveFieldComponent> };

function Builder() {
    builder = useFormFieldsAtom();
    active = { slide: useActiveSlideComponent(), field: useActiveFieldComponent() };
    React.useEffect(() => builder.initFormFields(form()), []);
    return null;
}

const ids = () => builder.formFields.map((slide) => slide.id);
const fieldIds = (pageIndex: number) => builder.formFields[pageIndex].properties!.fields!.map((f) => f.id);
const field = (id: string) => builder.formFields.flatMap((slide) => slide.properties!.fields!).find((f) => f.id === id)!;

describe('outline moves', () => {
    beforeEach(() => {
        render(
            <Provider>
                <Builder />
            </Provider>
        );
    });

    it('movePage reorders pages, renumbers them and is one undo step', async () => {
        await act(async () => void builder.movePage(2, 0));
        expect(ids()).toEqual(['p3', 'p1', 'p2']);
        expect(builder.formFields.map((s) => s.index)).toEqual([0, 1, 2]);
        await act(async () => builder.undo());
        expect(ids()).toEqual(['p1', 'p2', 'p3']);
        expect(builder.canUndo).toBe(false);
    });

    it('movePage keeps jump targets (ids) and drops jump conditions that now read a later page', async () => {
        let result: ReturnType<typeof builder.movePage> = null;
        // p2 first: its jump on "name" (now on a later page) cannot be evaluated when leaving it.
        await act(async () => void (result = builder.movePage(1, 0)));
        expect(ids()).toEqual(['p2', 'p1', 'p3']);
        const p2 = builder.formFields[0];
        expect(p2.properties?.jumps).toBeUndefined();
        // Show/hide on name and the pipe of name came before name: removed too.
        expect(field('city').properties?.logic).toBeUndefined();
        expect(JSON.stringify(field('greeting').title)).not.toContain('answerPipe');
        expect(result!.prunedReferences).toBe(3);
        // Unrelated rules stay: p3's jump to submit.
        expect(builder.formFields[2].properties?.jumps?.[0].target).toBe(JUMP_TARGET_SUBMIT);
        // One undo brings the order and the rules back.
        await act(async () => builder.undo());
        expect(ids()).toEqual(['p1', 'p2', 'p3']);
        expect(field('city').properties?.logic?.conditions).toHaveLength(1);
        expect(builder.formFields[1].properties?.jumps?.[0].target).toBe('p3');
    });

    it('movePage that keeps every source earlier keeps all logic', async () => {
        let result: ReturnType<typeof builder.movePage> = null;
        await act(async () => void (result = builder.movePage(2, 1)));
        expect(ids()).toEqual(['p1', 'p3', 'p2']);
        expect(result!.prunedReferences).toBe(0);
        expect(field('city').properties?.logic?.conditions).toHaveLength(1);
        expect(builder.formFields[2].properties?.jumps?.[0].target).toBe('p3');
    });

    it('moveFieldToPage moves a question across pages and renumbers both', async () => {
        await act(async () => void builder.moveFieldToPage('email', 2, 1));
        expect(fieldIds(0)).toEqual(['name']);
        expect(fieldIds(2)).toEqual(['notes', 'email']);
        expect(builder.formFields[2].properties!.fields!.map((f) => f.index)).toEqual([0, 1]);
        await act(async () => builder.undo());
        expect(fieldIds(0)).toEqual(['name', 'email']);
    });

    it('moveFieldToPage within a page', async () => {
        await act(async () => void builder.moveFieldToPage('greeting', 1, 0));
        expect(fieldIds(1)).toEqual(['greeting', 'city']);
        expect(builder.formFields[1].properties!.fields!.map((f) => f.index)).toEqual([0, 1]);
    });

    it('moving a source question after the questions that use it removes only those uses', async () => {
        let result: ReturnType<typeof builder.moveFieldToPage> = null;
        // "name" to the end of p2: city (show/hide) and greeting (pipe) now come before it;
        // p2's jump still reads an answer from its own page, which is allowed.
        await act(async () => void (result = builder.moveFieldToPage('name', 1, 2)));
        expect(fieldIds(1)).toEqual(['city', 'greeting', 'name']);
        expect(field('city').properties?.logic).toBeUndefined();
        expect(JSON.stringify(field('greeting').title)).not.toContain('answerPipe');
        expect(builder.formFields[1].properties?.jumps?.[0].conditions[0].fieldId).toBe('name');
        expect(result!.prunedReferences).toBe(2);
    });

    it('moving a question with logic later keeps a rule whose source is still earlier', async () => {
        let result: ReturnType<typeof builder.moveFieldToPage> = null;
        await act(async () => void (result = builder.moveFieldToPage('city', 2, 1)));
        expect(field('city').properties?.logic?.conditions[0].fieldId).toBe('name');
        expect(result!.prunedReferences).toBe(0);
    });

    it('moving a question to a later page drops a jump on its old page that read it', async () => {
        await act(async () => void builder.moveFieldToPage('name', 2, 0));
        expect(builder.formFields[1].properties?.jumps).toBeUndefined();
    });

    it('the selection follows a moved question', async () => {
        await act(async () => {
            active.slide.setActiveSlideComponent({ id: 'p1', index: 0 });
            active.field.setActiveFieldComponent({ id: 'email', index: 1 });
        });
        await act(async () => void builder.moveFieldToPage('email', 2, 0));
        expect(active.slide.activeSlideComponent).toEqual({ id: 'p3', index: 2 });
        expect(active.field.activeFieldComponent).toEqual({ id: 'email', index: 0 });
    });

    it('the selected page keeps its selection when pages move', async () => {
        await act(async () => active.slide.setActiveSlideComponent({ id: 'p1', index: 0 }));
        await act(async () => void builder.movePage(0, 2));
        expect(active.slide.activeSlideComponent).toEqual({ id: 'p1', index: 2 });
    });

    it('no-op moves change nothing and add no undo step', async () => {
        let page: unknown = 'x';
        let question: unknown = 'x';
        await act(async () => {
            page = builder.movePage(1, 1);
            question = builder.moveFieldToPage('email', 0, 1);
        });
        expect(page).toBeNull();
        expect(question).toBeNull();
        expect(builder.canUndo).toBe(false);
    });
});
