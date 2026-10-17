import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, useSetAtom, useStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useBuilderHydration } from '@app/store/jotai/builder-hydration';
import { fieldActions } from '@app/store/jotai/entity-hooks';
import { initialFieldsState } from '@app/store/jotai/field-selectors';
import { initialFormState } from '@app/store/jotai/form';
import { resetFromServerAtom } from '@app/store/jotai/form-document';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { deepCopy } from '@app/utils/object-utils';

import AutoSaveForm, { AUTOSAVE_DEBOUNCE_MS } from './audo-save-form';

const patchFormMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePatchV2FormMutation: () => [patchFormMock] };
});

const LOADED_VERSION = '2026-10-17T09:00:00.000+00:00';
const title = (text: string) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });

const loadedForm = () => ({
    formId: 'form-1',
    title: 'Loaded form',
    welcomePage: { title: 'Loaded form' },
    thankyouPage: [{ title: 'Thanks' }],
    fields: [{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: title('Name') }] } }]
});

let jotaiStore: ReturnType<typeof useStore> | null = null;

/**
 * The editor page as it loads and leaves: it loads the form and marks it
 * hydrated, and when it unmounts it lets go of the form and resets the
 * builder to an empty form (before its children's own cleanups run).
 */
function EditorPage() {
    jotaiStore = useStore();
    const reset = useSetAtom(resetFromServerAtom);
    const { setHydratedFormId } = useBuilderHydration();
    React.useEffect(() => {
        reset(loadedForm() as any);
        setHydratedFormId('form-1');
        return () => {
            setHydratedFormId(null);
            reset({ ...initialFormState, fields: deepCopy(initialFieldsState) } as any);
        };
    }, []);
    return <AutoSaveForm formId="form-1" />;
}

const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
const bodies = () => patchFormMock.mock.calls.map((call) => JSON.parse(call[0].body.get('form_body')));

function mount() {
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <EditorPage />
            </Provider>
        </ReduxProvider>
    );
}

describe('autosave when the editor is left', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        patchFormMock.mockReset().mockResolvedValue({ data: { formId: 'form-1', updatedAt: LOADED_VERSION } });
        store.dispatch(setWorkspace({ id: 'ws-1' } as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Loaded form', updatedAt: LOADED_VERSION } as any));
    });
    afterEach(() => vi.useRealTimers());

    it('saves nothing when nothing was edited', async () => {
        const view = mount();
        await advance(AUTOSAVE_DEBOUNCE_MS * 2);
        view.unmount();
        await advance(AUTOSAVE_DEBOUNCE_MS * 2);
        expect(patchFormMock).not.toHaveBeenCalled();
    });

    it('saves what was typed, not the emptied form, when left within the debounce', async () => {
        const view = mount();
        await advance(10);
        await act(async () => void fieldActions(jotaiStore!).updateTitle('q-1', title('Full name') as any));
        await advance(AUTOSAVE_DEBOUNCE_MS / 4);
        view.unmount();
        await advance(AUTOSAVE_DEBOUNCE_MS * 2);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        const [body] = bodies();
        expect(body.title).toBe('Loaded form');
        expect(body.fields.map((page: any) => page.id)).toEqual(['page-1']);
        expect(body.fields[0].properties.fields[0].title).toEqual(title('Full name'));
    });

    it('a save already sent is not followed by the emptied form', async () => {
        const view = mount();
        await advance(10);
        await act(async () => void fieldActions(jotaiStore!).updateTitle('q-1', title('Full name') as any));
        await advance(AUTOSAVE_DEBOUNCE_MS * 2);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        view.unmount();
        await advance(AUTOSAVE_DEBOUNCE_MS * 2);
        expect(patchFormMock).toHaveBeenCalledTimes(1);
        expect(bodies().every((body) => body.title === 'Loaded form')).toBe(true);
    });
});
