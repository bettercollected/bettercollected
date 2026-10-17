import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, useSetAtom } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const patchFormMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePatchV2FormMutation: () => [patchFormMock] };
});

import { FieldTypes } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useBuilderHydration } from '@app/store/jotai/builder-hydration';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { resetFromServerAtom } from '@app/store/jotai/form-document';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import AutoSaveForm from './audo-save-form';

const LOADED_VERSION = '2026-10-17T09:00:00.000+00:00';
const STORED = 'https://storage.example.org/forms-bucket/public/form-images/question.png';
const PAGE_IMAGE = 'https://storage.example.org/forms-bucket/public/form-images/page.png';

const loadedForm = () => ({
    formId: 'form-1',
    title: 'Loaded form',
    welcomePage: { title: 'Loaded form', imageUrl: STORED },
    thankyouPage: [{ title: 'Thanks' }],
    fields: [
        {
            id: 'page-1',
            index: 0,
            type: FieldTypes.SLIDE,
            imageUrl: PAGE_IMAGE,
            properties: {
                fields: [
                    { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', imageUrl: STORED },
                    { id: 'q-2', index: 1, type: FieldTypes.SHORT_TEXT, title: 'Email' }
                ]
            }
        },
        { id: 'page-2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-3', index: 0, type: FieldTypes.SHORT_TEXT, title: 'City' }] } }
    ]
});

const editor: { fields?: ReturnType<typeof useFormFieldsAtom>; form?: ReturnType<typeof useFormState> } = {};

/** Loads the form as the editor page does, then marks it hydrated. */
function EditorPage() {
    editor.fields = useFormFieldsAtom();
    editor.form = useFormState();
    const reset = useSetAtom(resetFromServerAtom);
    const { setHydratedFormId } = useBuilderHydration();
    React.useEffect(() => {
        reset(loadedForm() as any);
        setHydratedFormId('form-1');
    }, []);
    return null;
}

const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
const lastBody = () => JSON.parse(patchFormMock.mock.calls.at(-1)[0].body.get('form_body'));

describe('autosave after undoing a delete', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        patchFormMock.mockReset().mockResolvedValue({ data: { formId: 'form-1', updatedAt: LOADED_VERSION } });
        store.dispatch(setWorkspace({ id: 'ws-1' } as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Loaded form', updatedAt: LOADED_VERSION } as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <EditorPage />
                    <AutoSaveForm formId="form-1" />
                </Provider>
            </ReduxProvider>
        );
    });
    afterEach(() => vi.useRealTimers());

    it('saves the question back, with its uploaded image', async () => {
        await act(async () => editor.fields!.deleteField(0, 0));
        // The delete is saved first; then the undo must be saved too.
        await advance(1000);
        expect(lastBody().fields[0].properties.fields.map((f: any) => f.id)).toEqual(['q-2']);
        await act(async () => editor.fields!.undo());
        await advance(1000);
        const page = lastBody().fields[0];
        expect(page.properties.fields.map((f: any) => f.id)).toEqual(['q-1', 'q-2']);
        expect(page.properties.fields[0].imageUrl).toBe(STORED);
    });

    it('saves the page back, with its uploaded layout image', async () => {
        await act(async () => editor.fields!.deleteSlide(0));
        await advance(1000);
        expect(lastBody().fields.map((p: any) => p.id)).toEqual(['page-2']);
        await act(async () => editor.fields!.undo());
        await advance(1000);
        const body = lastBody();
        expect(body.fields.map((p: any) => p.id)).toEqual(['page-1', 'page-2']);
        expect(body.fields[0].imageUrl).toBe(PAGE_IMAGE);
        expect(body.fields[0].properties.fields[0].imageUrl).toBe(STORED);
    });

    it('saves a replaced welcome image back', async () => {
        await act(async () => editor.form!.updateWelcomePageImage('https://storage.example.org/forms-bucket/public/form-images/new.png'));
        await advance(1000);
        await act(async () => editor.fields!.undo());
        await advance(1000);
        expect(lastBody().welcomePage.imageUrl).toBe(STORED);
    });

    it('a default written on mount is no undo step', async () => {
        await act(async () => editor.form!.setFormDescription('', { undoable: false }));
        expect(editor.fields!.canUndo).toBe(false);
        expect(editor.form!.formState.welcomePage?.description).toBe('');
    });
});
