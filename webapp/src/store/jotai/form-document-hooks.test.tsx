import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, useSetAtom } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import form200 from '@app/test/fixtures/form-200.json';

import useFormFieldsAtom, { UNDO_COALESCE_MS } from './field-selectors';
import { useFormState } from './form';
import { resetFromServerAtom } from './form-document';

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; form?: ReturnType<typeof useFormState> } = {};

function Editor() {
    const builder = useFormFieldsAtom();
    const form = useFormState();
    const reset = useSetAtom(resetFromServerAtom);
    React.useEffect(() => {
        seen.builder = builder;
        seen.form = form;
    });
    React.useEffect(() => reset(structuredClone(form200) as any), []);
    return null;
}

describe('the builder hooks on the form document', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        render(
            <Provider>
                <Editor />
            </Provider>
        );
    });
    afterEach(() => vi.useRealTimers());

    it('loading through resetFromServer leaves nothing to undo', () => {
        expect(seen.form!.formState.title).toBe(form200.title);
        expect(seen.builder!.formFields).toHaveLength(20);
        expect(seen.builder!.canUndo).toBe(false);
    });

    it('the toolbar undo covers form-level edits too, typing being one step', async () => {
        for (const title of ['N', 'Ne', 'New']) {
            await act(async () => seen.form!.setFormTitle(title));
            vi.advanceTimersByTime(100);
        }
        vi.advanceTimersByTime(UNDO_COALESCE_MS);
        await act(async () => seen.form!.setThankYouPageTitle(0, 'Bye'));
        await act(async () => seen.builder!.updateDescription(0, 0, 'Help text'));
        expect(seen.builder!.canUndo).toBe(true);

        await act(async () => seen.builder!.undo());
        expect(seen.builder!.formFields[0].properties!.fields![0].description).toBeUndefined();
        await act(async () => seen.builder!.undo());
        expect(seen.form!.formState.thankyouPage?.[0].title).toBe('Thanks');
        await act(async () => seen.builder!.undo());
        expect(seen.form!.formState.title).toBe(form200.title);
        expect(seen.builder!.canUndo).toBe(false);

        await act(async () => seen.builder!.redo());
        expect(seen.form!.formState.title).toBe('New');
    });
});
