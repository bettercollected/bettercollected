import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, useAtomValue, useSetAtom } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import form200 from '@app/test/fixtures/form-200.json';

import useFormFieldsAtom, { UNDO_COALESCE_MS } from './field-selectors';
import { useFormState } from './form';
import { DocHistory, docHistoryAtom, resetFromServerAtom } from './form-document';

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; form?: ReturnType<typeof useFormState>; history?: DocHistory } = {};

function Editor() {
    const builder = useFormFieldsAtom();
    const form = useFormState();
    const reset = useSetAtom(resetFromServerAtom);
    const history = useAtomValue(docHistoryAtom);
    React.useEffect(() => {
        seen.builder = builder;
        seen.form = form;
        seen.history = history;
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

    const typeRun = async (texts: string[], write: (text: string) => void) => {
        for (const text of texts) {
            await act(async () => write(text));
            vi.advanceTimersByTime(100);
        }
    };
    const steps = () => seen.history!.steps;

    it("typing a jump's or a show/hide condition's value is one undo step each", async () => {
        const jump = (value: string) => [{ operator: 'AND', target: 'page-03', conditions: [{ fieldId: 'p01-q01', comparison: 'IS_EQUAL', value }] }] as any;
        await typeRun(['f', 'fr', 'fri', 'friend'], (value) => seen.builder!.updateSlideJumps(0, jump(value)));
        expect(steps()).toHaveLength(1);
        const logic = (value: string) => ({ action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'p01-q01', comparison: 'IS_EQUAL', value }] }) as any;
        await typeRun(['w', 'we', 'web'], (value) => seen.builder!.updateFieldConditionalLogic(2, 0, logic(value)));
        expect(steps()).toHaveLength(2);
        await act(async () => seen.builder!.undo());
        await act(async () => seen.builder!.undo());
        expect(seen.builder!.formFields[0].properties?.jumps).toBeUndefined();
        expect(seen.builder!.canUndo).toBe(false);
    });

    it('writing the placeholder a question already has is no undo step', async () => {
        const placeholder = seen.builder!.formFields[0].properties!.fields![0].properties?.placeholder;
        await act(async () => seen.builder!.updateFieldPlaceholder(0, 0, placeholder as string));
        await act(async () => seen.builder!.updateFieldPlaceholder(1, 0, ''));
        expect(steps()).toHaveLength(0);
    });

    it('a long typing run keeps one keystroke of ops in its step', async () => {
        await typeRun(['N', 'Ne'], (title) => seen.form!.setFormTitle(title));
        const firstInverse = steps()[0].inverse.length;
        await typeRun(['New', 'New ', 'New t', 'New ti', 'New tit', 'New title'], (title) => seen.form!.setFormTitle(title));
        expect(steps()).toHaveLength(1);
        // The last keystroke's ops, the first keystroke's inverse: no growth.
        expect(steps()[0].forward.map((op) => op.op)).toEqual(['update_form_info', 'update_welcome_page']);
        expect(steps()[0].inverse).toHaveLength(firstInverse);
        vi.advanceTimersByTime(UNDO_COALESCE_MS);
        await typeRun(['T', 'Th', 'Tha', 'Than', 'Thank', 'Thanks', 'Thanks!', 'Thanks!!'], (title) => seen.form!.setThankYouPageTitle(0, title));
        expect(steps()).toHaveLength(2);
        expect(steps()[1].forward.map((op) => op.op)).toEqual(['set_endings']);
        await act(async () => seen.builder!.undo());
        await act(async () => seen.builder!.undo());
        expect(seen.form!.formState.title).toBe(form200.title);
        expect(seen.form!.formState.thankyouPage?.[0].title).toBe('Thanks');
    });
});
