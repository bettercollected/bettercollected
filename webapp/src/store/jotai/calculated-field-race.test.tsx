import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, useAtomValue, useSetAtom } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const patchFormMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePatchV2FormMutation: () => [patchFormMock] };
});

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useBuilderHydration } from '@app/store/jotai/builder-hydration';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { DocHistory, docHistoryAtom, formDocAtom, resetFromServerAtom } from '@app/store/jotai/form-document';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import AutoSaveForm from '@app/views/molecules/form-builder/audo-save-form';

const VERSION = '2026-10-17T09:00:00.000+00:00';

const loadedForm = () => ({
    formId: 'form-1',
    title: 'Order',
    fields: [{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'qty', index: 0, type: FieldTypes.NUMBER, title: 'Quantity' }] } }]
});
const calculation = (): StandardFormFieldDto => ({ id: 'total', index: 1, type: FieldTypes.CALCULATED, title: 'Total', properties: { fields: [] } }) as StandardFormFieldDto;
const formula = (factor: number) => ({ '*': [{ var: 'qty' }, factor] });

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; history?: DocHistory; doc?: any } = {};

function Editor() {
    const builder = useFormFieldsAtom();
    const history = useAtomValue(docHistoryAtom);
    const doc = useAtomValue(formDocAtom);
    const reset = useSetAtom(resetFromServerAtom);
    const { setHydratedFormId } = useBuilderHydration();
    seen.builder = builder;
    seen.history = history;
    seen.doc = doc;
    React.useEffect(() => {
        reset(loadedForm() as any);
        setHydratedFormId('form-1');
    }, []);
    return null;
}

const expressionInDoc = () => seen.doc.fields[0].properties.fields[1]?.properties?.expression;
const expressionInBuilder = () => seen.builder!.formFields[0].properties!.fields![1]?.properties?.expression;

describe('typing the first formula into a just-inserted calculation', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        // The server answers each save after a while, with the form as saved.
        patchFormMock.mockReset().mockImplementation(async ({ body }: any) => {
            await new Promise((resolve) => setTimeout(resolve, 150));
            return { data: { ...JSON.parse(body.get('form_body')), formId: 'form-1', updatedAt: VERSION } };
        });
        store.dispatch(setWorkspace({ id: 'ws-1' } as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Order', updatedAt: VERSION } as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Editor />
                    <AutoSaveForm formId="form-1" />
                </Provider>
            </ReduxProvider>
        );
    });
    afterEach(() => vi.useRealTimers());

    it('keeps the formula and its step when the insert is saved between keystrokes', async () => {
        await act(async () => seen.builder!.addFieldAt(calculation(), 0, 1));
        // the insert's save goes out, its answer lands while the formula is typed
        await act(async () => vi.advanceTimersByTimeAsync(1000));
        for (const factor of [2, 20, 200]) {
            await act(async () => seen.builder!.updateFieldProperty(1, 0, 'expression', formula(factor)));
            await act(async () => vi.advanceTimersByTimeAsync(80));
        }
        await act(async () => vi.advanceTimersByTimeAsync(3000));
        expect(patchFormMock).toHaveBeenCalledTimes(2);
        expect(expressionInDoc()).toEqual(formula(200));
        expect(expressionInBuilder()).toEqual(formula(200));
        expect(seen.history!.steps.map((step) => step.coalesceKey ?? null)).toEqual([null, 'property:total:expression']);
    });

    it("a formula reverted by the input's own undo while typing leaves no empty step behind", async () => {
        await act(async () => seen.builder!.addFieldAt(calculation(), 0, 1));
        for (const factor of [2, 20]) await act(async () => seen.builder!.updateFieldProperty(1, 0, 'expression', formula(factor)));
        // Ctrl+Z inside the formula box: the textarea's own undo empties it,
        // and the inspector writes "no formula" within the same typing run.
        await act(async () => seen.builder!.updateFieldProperty(1, 0, 'expression', undefined));
        expect(expressionInDoc()).toBeUndefined();
        expect(seen.history!.steps).toHaveLength(1);
        // The next toolbar undo takes back the insert, not an edit that changed nothing.
        await act(async () => seen.builder!.undo());
        expect(seen.doc.fields[0].properties.fields.map((f: any) => f.id)).toEqual(['qty']);
    });

    it('an undo landing while the formula is typed takes back the typing so far; typing on is a new step', async () => {
        await act(async () => seen.builder!.addFieldAt(calculation(), 0, 1));
        for (const factor of [2, 20]) await act(async () => seen.builder!.updateFieldProperty(1, 0, 'expression', formula(factor)));
        await act(async () => seen.builder!.undo());
        expect(expressionInDoc()).toBeUndefined();
        expect(seen.builder!.canRedo).toBe(true);
        // the next keystroke (within the same second) starts a new step and drops the redo
        await act(async () => seen.builder!.updateFieldProperty(1, 0, 'expression', formula(200)));
        expect(expressionInDoc()).toEqual(formula(200));
        expect(seen.history!.steps.map((step) => step.coalesceKey ?? null)).toEqual([null, 'property:total:expression']);
        expect(seen.builder!.canRedo).toBe(false);
        await act(async () => seen.builder!.undo());
        expect(expressionInDoc()).toBeUndefined();
        expect(seen.doc.fields[0].properties.fields.map((f: any) => f.id)).toEqual(['qty', 'total']);
    });

    it('a handler from a render before an undo or redo still edits the current form', async () => {
        await act(async () => seen.builder!.addFieldAt(calculation(), 0, 1));
        await act(async () => seen.builder!.updateFieldProperty(1, 0, 'expression', formula(2)));
        await act(async () => vi.advanceTimersByTimeAsync(1500));
        // A handler captured before the undo and redo (a scripted Ctrl+Z / Ctrl+Y
        // running while the inspector is typed into).
        const stale = seen.builder!;
        await act(async () => seen.builder!.undo());
        await act(async () => seen.builder!.redo());
        await act(async () => stale.updateFieldProperty(1, 0, 'expression', formula(3)));
        expect(expressionInDoc()).toEqual(formula(3));
        expect(expressionInBuilder()).toEqual(formula(3));
        expect(seen.history!.steps).toHaveLength(3);
        await act(async () => seen.builder!.undo());
        expect(expressionInDoc()).toEqual(formula(2));
    });
});
