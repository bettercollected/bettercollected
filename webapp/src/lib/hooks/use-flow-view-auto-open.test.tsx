import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { builderHydratedFormIdAtom } from '@app/store/jotai/builder-hydration';
import { builderFieldsAtom, resetFromServerAtom } from '@app/store/jotai/form-document';

import { useFlowViewAutoOpen } from './use-flow-view-auto-open';

const FORM_ID = 'form-1';

const question = (withLogic: boolean) => ({
    id: 'q-2',
    index: 0,
    type: FieldTypes.SHORT_TEXT,
    title: 'Why?',
    properties: withLogic ? { logic: { operator: 'and', conditions: [{ fieldId: 'q-1', operator: 'is', value: 'Yes' }] } } : {}
});

const pages = (withLogic: boolean) => [
    { id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-1', index: 0, type: FieldTypes.YES_NO, title: 'Coming?' }] } },
    { id: 'page-2', index: 1, type: FieldTypes.SLIDE, properties: { fields: [question(withLogic)] } }
];

function Probe({ formId, onOpen }: { formId: string; onOpen: () => void }) {
    useFlowViewAutoOpen(formId, onOpen);
    return null;
}

/** Mounts the builder chrome, then loads the form as the editor page does (pages first, then marked loaded). */
function openForm({ withLogic }: { withLogic: boolean }) {
    const store = createStore();
    const onOpen = vi.fn();
    render(
        <Provider store={store}>
            <Probe formId={FORM_ID} onOpen={onOpen} />
        </Provider>
    );
    act(() => {
        store.set(resetFromServerAtom, { formId: FORM_ID, title: 'Event', fields: pages(withLogic) } as any);
        store.set(builderHydratedFormIdAtom, FORM_ID);
    });
    return { store, onOpen };
}

describe('the Flow view opening by itself', () => {
    beforeEach(() => localStorage.clear());
    afterEach(() => localStorage.clear());

    it('opens for a form that already branches when it is opened', () => {
        const { onOpen } = openForm({ withLogic: true });
        expect(onOpen).toHaveBeenCalledTimes(1);
    });

    it('stays shut while the form loads: an empty builder is not the form', () => {
        const store = createStore();
        const onOpen = vi.fn();
        render(
            <Provider store={store}>
                <Probe formId={FORM_ID} onOpen={onOpen} />
            </Provider>
        );
        // Pages arrive before the editor marks the form loaded.
        act(() => store.set(resetFromServerAtom, { formId: FORM_ID, title: 'Event', fields: pages(false) } as any));
        act(() => store.set(builderHydratedFormIdAtom, FORM_ID));
        expect(onOpen).not.toHaveBeenCalled();
    });

    it('does not open when the creator adds the first logic while editing', () => {
        const { store, onOpen } = openForm({ withLogic: false });
        expect(onOpen).not.toHaveBeenCalled();

        act(() => store.set(builderFieldsAtom, pages(true) as any));
        expect(onOpen).not.toHaveBeenCalled();
    });

    it('keeps the page view a creator chose for this form', () => {
        localStorage.setItem(`bc-default-view-${FORM_ID}`, 'page');
        const { onOpen } = openForm({ withLogic: true });
        expect(onOpen).not.toHaveBeenCalled();
    });
});
