// Inserting a field focuses its title a moment later, once the canvas shows
// it. That moment must not outlive the builder: a timer left running after
// unmount fires on a document that may be gone (a test file's jsdom torn
// down), so the hook cancels its timers when it unmounts.
import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { resetFromServerAtom } from '@app/store/jotai/form-document';

import { useInsertField } from './use-insert-field';

const seen: { insert?: ReturnType<typeof useInsertField>['insert'] } = {};

function Builder() {
    seen.insert = useInsertField().insert;
    return null;
}

function renderBuilder() {
    const store = createStore();
    store.set(resetFromServerAtom, { formId: 'form-1', title: 'Form', fields: [{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [] } }] } as any);
    store.set(activeSlideAtom, { id: 'page-1', index: 0 });
    return render(
        <Provider store={store}>
            <Builder />
        </Provider>
    );
}

/** What the canvas shows for a question: its wrapper and its focusable body. */
function showOnCanvas(field: StandardFormFieldDto) {
    const wrapper = document.body.appendChild(document.createElement('div'));
    wrapper.id = `scroll-field-${field.id}`;
    const body = wrapper.appendChild(document.createElement('div'));
    body.setAttribute('data-canvas-field', '');
    body.tabIndex = 0;
    return { wrapper, body };
}

describe('inserting a field', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => {
        vi.useRealTimers();
        document.body.innerHTML = '';
    });

    it('focuses the new field once the canvas shows it', async () => {
        renderBuilder();
        let field: StandardFormFieldDto | null = null;
        act(() => {
            field = seen.insert!({ type: FieldTypes.SHORT_TEXT, name: 'Short answer' });
        });
        expect(field).not.toBeNull();
        const { body } = showOnCanvas(field!);
        await act(async () => vi.advanceTimersByTimeAsync(50));
        expect(document.activeElement).toBe(body);
    });

    it('leaves no timer running once the builder unmounts', async () => {
        const { unmount } = renderBuilder();
        act(() => {
            seen.insert!({ type: FieldTypes.SHORT_TEXT, name: 'Short answer' });
        });
        expect(vi.getTimerCount()).toBeGreaterThan(0);
        unmount();
        expect(vi.getTimerCount()).toBe(0);
    });

    it('does not touch the document after unmount', async () => {
        const { unmount } = renderBuilder();
        let field: StandardFormFieldDto | null = null;
        act(() => {
            field = seen.insert!({ type: FieldTypes.SHORT_TEXT, name: 'Short answer' });
        });
        showOnCanvas(field!);
        unmount();
        const lookup = vi.spyOn(document, 'getElementById');
        await vi.advanceTimersByTimeAsync(2000);
        expect(lookup).not.toHaveBeenCalled();
        lookup.mockRestore();
    });
});
