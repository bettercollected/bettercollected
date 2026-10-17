import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const patchFormMock = vi.fn();
const publishFormMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        usePatchV2FormMutation: () => [patchFormMock],
        usePublishV2FormMutation: () => [publishFormMock, { isLoading: false }]
    };
});
const openDialogMock = vi.fn();
vi.mock('@app/lib/hooks/use-dialog-modal', () => ({ useDialogModal: () => ({ openDialogModal: openDialogMock }) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/ws/dashboard/forms/form-1/edit' }));

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Toaster } from '@app/shadcn/components/ui/toaster';
import { setForm } from '@app/store/forms/slice';
import { useAutosaveStatus } from '@app/store/jotai/autosave-status';
import { useBuilderHydration } from '@app/store/jotai/builder-hydration';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import AutoSaveForm, { flushAutosave, saveOutcomeOf } from './audo-save-form';
import PublishButton from './publish-button';

const LOADED_VERSION = '2026-10-17T09:00:00.000+00:00';
const SAVED_VERSION = '2026-10-17T09:00:02.000+00:00';

const page = (): StandardFormFieldDto[] => [
    {
        id: 'page-1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: { fields: [{ id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', description: '' }] }
    } as StandardFormFieldDto
];

// The builder's edit functions, captured from inside the Provider.
const editor: { fields?: ReturnType<typeof useFormFieldsAtom>; status?: string } = {};

/** Does what the editor page does: load the form into the builder state, then mark it hydrated. */
function EditorPage({ hydrate = true }: { hydrate?: boolean }) {
    const fields = useFormFieldsAtom();
    const { setFormState } = useFormState();
    const { setHydratedFormId } = useBuilderHydration();
    const { autosaveStatus } = useAutosaveStatus();
    editor.fields = fields;
    editor.status = autosaveStatus.state;
    React.useEffect(() => {
        setFormState((prev) => ({ ...prev, title: 'Loaded form' }));
        fields.initFormFields(page());
        if (hydrate) setHydratedFormId('form-1');
    }, []);
    return null;
}

function renderEditor({ hydrate = true, publish = false } = {}) {
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <EditorPage hydrate={hydrate} />
                <AutoSaveForm formId="form-1" />
                {publish && <PublishButton fields={editor.fields?.formFields} />}
                <Toaster />
            </Provider>
        </ReduxProvider>
    );
}

const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
const lastBody = () => JSON.parse(patchFormMock.mock.calls.at(-1)[0].body.get('form_body'));
const lastVersion = () => patchFormMock.mock.calls.at(-1)[0].body.get('expected_updated_at');
const saved = (overrides: Record<string, any> = {}) => ({ data: { formId: 'form-1', updatedAt: SAVED_VERSION, ...overrides } });

function beforeUnloadPrevented() {
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
}

describe('AutoSaveForm', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        patchFormMock.mockReset().mockResolvedValue(saved());
        publishFormMock.mockReset().mockResolvedValue({ data: { formId: 'form-1' } });
        openDialogMock.mockReset();
        store.dispatch(setWorkspace({ id: 'ws-1' } as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Loaded form', updatedAt: LOADED_VERSION } as any));
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('opening a form saves nothing, however long it takes', async () => {
        renderEditor();
        await advance(10_000);
        expect(patchFormMock).not.toHaveBeenCalled();
        expect(beforeUnloadPrevented()).toBe(false);
    });

    it('nothing is saved before the editor says the form is loaded', async () => {
        renderEditor({ hydrate: false });
        await act(async () => editor.fields!.updateDescription(0, 0, 'typed early'));
        await advance(5000);
        expect(patchFormMock).not.toHaveBeenCalled();
    });

    it('an edit right after opening is saved, with the version it builds on', async () => {
        renderEditor();
        await act(async () => editor.fields!.updateDescription(0, 0, 'Your full name'));
        await advance(999);
        expect(patchFormMock).not.toHaveBeenCalled();
        await advance(1);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        expect(lastBody().fields[0].properties.fields[0].description).toBe('Your full name');
        expect(lastVersion()).toBe(LOADED_VERSION);
        await advance(0);
        expect(editor.status).toBe('saved');

        // the next save builds on what the server returned
        await act(async () => editor.fields!.updateDescription(0, 0, 'Your name'));
        await advance(1000);
        expect(lastVersion()).toBe(SAVED_VERSION);
    });

    it('deleting every page is saved', async () => {
        renderEditor();
        await act(async () => editor.fields!.deleteSlide(0));
        await advance(1000);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        expect(lastBody().fields).toEqual([]);
    });

    it('warns before leaving while an edit is not stored yet', async () => {
        let resolveSave: (value: any) => void = () => {};
        patchFormMock.mockImplementation(() => new Promise((resolve) => (resolveSave = resolve)));
        renderEditor();
        await act(async () => editor.fields!.updateDescription(0, 0, 'pending'));
        // waiting for the debounce
        expect(beforeUnloadPrevented()).toBe(true);
        await advance(1000);
        // in flight
        expect(beforeUnloadPrevented()).toBe(true);
        await act(async () => resolveSave(saved()));
        expect(beforeUnloadPrevented()).toBe(false);
    });

    it('retries a save that did not reach the server', async () => {
        patchFormMock.mockResolvedValueOnce({ error: { status: 'FETCH_ERROR' } });
        renderEditor();
        await act(async () => editor.fields!.updateDescription(0, 0, 'offline edit'));
        await advance(1000);
        expect(editor.status).toBe('retrying');
        expect(screen.queryByText('Offline — retrying…')).toBeNull(); // the label lives in the navbar
        expect(beforeUnloadPrevented()).toBe(true);
        await advance(1000);
        expect(patchFormMock).toHaveBeenCalledTimes(2);
        expect(lastBody().fields[0].properties.fields[0].description).toBe('offline edit');
        expect(editor.status).toBe('saved');
    });

    it('a form changed elsewhere is never overwritten: it offers to reload the latest', async () => {
        patchFormMock.mockResolvedValueOnce({ error: { status: 409, data: { code: 'form_changed' } } });
        const reload = vi.fn();
        const location = window.location;
        Object.defineProperty(window, 'location', { configurable: true, value: { ...location, reload } });
        try {
            renderEditor();
            await act(async () => editor.fields!.updateDescription(0, 0, 'mine'));
            await advance(1000);
            expect(screen.getByRole('dialog', { name: 'This form changed elsewhere' })).toBeInTheDocument();
            expect(editor.status).toBe('conflict');

            await act(async () => editor.fields!.updateDescription(0, 0, 'mine, more'));
            await advance(60_000);
            expect(patchFormMock).toHaveBeenCalledTimes(1);

            fireEvent.click(screen.getByRole('button', { name: 'Reload latest' }));
            expect(reload).toHaveBeenCalledTimes(1);
            // reloading on purpose is not stopped by the unsaved-changes guard
            expect(beforeUnloadPrevented()).toBe(false);
        } finally {
            Object.defineProperty(window, 'location', { configurable: true, value: location });
        }
    });
});

describe('publishing from the editor', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        patchFormMock.mockReset().mockResolvedValue(saved());
        publishFormMock.mockReset().mockResolvedValue({ data: { formId: 'form-1' } });
        store.dispatch(setWorkspace({ id: 'ws-1' } as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Loaded form', updatedAt: LOADED_VERSION, settings: { publishChecksVersion: null } } as any));
    });
    afterEach(() => vi.useRealTimers());

    it('saves the pending edit first and publishes only once it is stored', async () => {
        const order: string[] = [];
        let resolveSave: (value: any) => void = () => {};
        patchFormMock.mockImplementation(() => {
            order.push('save');
            return new Promise((resolve) => (resolveSave = resolve));
        });
        publishFormMock.mockImplementation(async () => {
            order.push('publish');
            return { data: { formId: 'form-1' } };
        });
        renderEditor({ publish: true });
        await act(async () => editor.fields!.updateDescription(0, 0, 'last-second fix'));
        // well inside the debounce
        fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        await advance(0);
        expect(order).toEqual(['save']);
        expect(lastBody().fields[0].properties.fields[0].description).toBe('last-second fix');
        await advance(5000);
        expect(publishFormMock).not.toHaveBeenCalled();
        await act(async () => resolveSave(saved()));
        await advance(0);
        expect(order).toEqual(['save', 'publish']);
    });

    it('does not publish over a form changed elsewhere', async () => {
        patchFormMock.mockResolvedValue({ error: { status: 409 } });
        renderEditor({ publish: true });
        await act(async () => editor.fields!.updateDescription(0, 0, 'mine'));
        fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        await advance(0);
        expect(publishFormMock).not.toHaveBeenCalled();
        expect(screen.getAllByText(/changed somewhere else/).length).toBeGreaterThan(0);
    });

    it('does not publish while the latest edit cannot be stored', async () => {
        patchFormMock.mockResolvedValue({ error: { status: 'FETCH_ERROR' } });
        renderEditor({ publish: true });
        await act(async () => editor.fields!.updateDescription(0, 0, 'offline'));
        fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        await advance(25_000);
        expect(publishFormMock).not.toHaveBeenCalled();
        expect(screen.getByText(/aren't saved yet/)).toBeInTheDocument();
    });

    it('with no editor open there is nothing to wait for', async () => {
        await expect(flushAutosave()).resolves.toBe('saved');
    });
});

describe('saveOutcomeOf', () => {
    it('maps the API answer onto the queue', () => {
        expect(saveOutcomeOf({ data: { updatedAt: 'v' } })).toEqual({ kind: 'saved', version: 'v' });
        expect(saveOutcomeOf({ error: { status: 409 } })).toEqual({ kind: 'conflict' });
        expect(saveOutcomeOf({ error: { status: 'FETCH_ERROR' } })).toEqual({ kind: 'retryable' });
        expect(saveOutcomeOf({ error: { status: 503 } })).toEqual({ kind: 'retryable' });
        expect(saveOutcomeOf({ error: { status: 422 } })).toEqual({ kind: 'failed' });
        expect(saveOutcomeOf({ error: { status: 403 } })).toEqual({ kind: 'failed' });
    });
});
