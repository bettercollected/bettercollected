import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, useAtomValue, useSetAtom } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';

import useFormFieldsAtom, { UNDO_COALESCE_MS } from './field-selectors';
import { DocHistory, SET_FIELDS, docHistoryAtom, formDocAtom, resetFromServerAtom } from './form-document';

const loadedForm = () => ({
    formId: 'form-1',
    title: 'Order',
    fields: [
        {
            id: 'page-1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [
                    { id: 'qty', index: 0, type: FieldTypes.NUMBER, title: 'Quantity' },
                    { id: 'total', index: 1, type: FieldTypes.CALCULATED, title: 'Total', properties: { expression: { '*': [{ var: 'qty' }, 2] } } }
                ]
            }
        }
    ]
});

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; history?: DocHistory; doc?: any } = {};

function Editor() {
    const builder = useFormFieldsAtom();
    const history = useAtomValue(docHistoryAtom);
    const doc = useAtomValue(formDocAtom);
    const reset = useSetAtom(resetFromServerAtom);
    React.useEffect(() => {
        seen.builder = builder;
        seen.history = history;
        seen.doc = doc;
    });
    React.useEffect(() => reset(loadedForm() as any), []);
    return null;
}

const total = () => seen.doc.fields[0].properties.fields[1].properties;

describe('calculated field edits', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        render(
            <Provider>
                <Editor />
            </Provider>
        );
    });
    afterEach(() => vi.useRealTimers());

    it('expression, format, hide and unanswered-as-0 go through ops and undo one by one', async () => {
        const set = async (property: string, value: unknown) => {
            await act(async () => seen.builder!.updateFieldProperty(1, 0, property, value));
            vi.advanceTimersByTime(UNDO_COALESCE_MS);
        };
        // Typing a formula: one step.
        for (const factor of [3, 30, 300]) await act(async () => seen.builder!.updateFieldProperty(1, 0, 'expression', { '*': [{ var: 'qty' }, factor] }));
        vi.advanceTimersByTime(UNDO_COALESCE_MS);
        await set('format', { style: 'currency', currency: 'EUR', decimals: 2 });
        await set('hiddenFromRespondents', true);
        await set('unansweredAsZero', true);
        expect(seen.history!.steps).toHaveLength(4);
        expect(seen.history!.steps.flatMap((step) => step.forward.map((op) => op.op))).not.toContain(SET_FIELDS);
        expect(total()).toMatchObject({ expression: { '*': [{ var: 'qty' }, 300] }, hiddenFromRespondents: true, unansweredAsZero: true });

        await act(async () => seen.builder!.undo());
        expect(total().unansweredAsZero).toBeUndefined();
        await act(async () => seen.builder!.undo());
        expect(total().hiddenFromRespondents).toBeUndefined();
        await act(async () => seen.builder!.undo());
        expect(total().format).toBeUndefined();
        await act(async () => seen.builder!.undo());
        expect(total().expression).toEqual({ '*': [{ var: 'qty' }, 2] });
        expect(seen.builder!.formFields[0].properties!.fields![1].properties?.expression).toEqual({ '*': [{ var: 'qty' }, 2] });
        expect(seen.builder!.canUndo).toBe(false);
    });
});
