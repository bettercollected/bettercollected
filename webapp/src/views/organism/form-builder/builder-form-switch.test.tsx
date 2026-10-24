import React, { Suspense } from 'react';

import { act, render } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import FormEditPage from '@app/app/(admin-portal)/(no-layout)/[workspace_name]/dashboard/forms/[form_id]/edit/_components/form-edit-page';
import { FieldTypes } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { store as reduxStore } from '@app/store/store';

/**
 * Opening a form while the builder still holds a selection from the form
 * edited before (a question on its second page, say): the builder shows the
 * new form, it does not crash on a page this form does not have.
 */

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/form-new/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));

const newForm = {
    formId: 'form-new',
    title: 'Classic form',
    welcomePage: { title: 'Classic form' },
    thankyouPage: [{ id: 'ending-1', title: 'Thanks' }],
    fields: [
        {
            id: 'new-page-1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: { fields: [{ id: 'new-q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name' }] }
        }
    ]
};

beforeAll(() => {
    const rects = () => ({ length: 0, item: () => null, [Symbol.iterator]: [][Symbol.iterator] }) as unknown as DOMRectList;
    const rect = () => ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }) as DOMRect;
    Range.prototype.getClientRects = rects;
    Range.prototype.getBoundingClientRect = rect;
    if (!Element.prototype.getClientRects) Element.prototype.getClientRects = rects;
    if (!document.elementFromPoint) document.elementFromPoint = () => null;
    if (!(globalThis as any).ResizeObserver) {
        (globalThis as any).ResizeObserver = class {
            observe() {}
            unobserve() {}
            disconnect() {}
        };
    }
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
});

afterAll(() => {
    vi.useRealTimers();
});

afterEach(() => {
    reduxStore.dispatch(setForm({} as any));
});

describe('opening another form in the builder', () => {
    it('drops a page and question selection from the form edited before', async () => {
        const jotai = createStore();
        // Left from the other form: its second page, a question on it.
        jotai.set(activeSlideAtom, { id: 'old-page-2', index: 1 });
        jotai.set(activeFieldAtom, { id: 'old-q-3', index: 0 });
        reduxStore.dispatch(setForm(structuredClone(newForm) as any));
        const errors = vi.spyOn(console, 'error').mockImplementation(() => undefined);
        let container: HTMLElement | undefined;
        await act(async () => {
            ({ container } = render(
                <ReduxProvider store={reduxStore}>
                    <Provider store={jotai}>
                        <Suspense fallback={null}>
                            <FormEditPage params={Promise.resolve({ form_id: newForm.formId })} />
                        </Suspense>
                    </Provider>
                </ReduxProvider>
            ));
        });
        for (let i = 0; i < 5; i++) {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(10);
            });
        }
        const crashes = errors.mock.calls.filter((call) => String(call[0]).includes('properties'));
        errors.mockRestore();

        expect(crashes).toEqual([]);
        expect(jotai.get(activeSlideAtom)).toEqual({ id: 'new-page-1', index: 0 });
        expect(jotai.get(activeFieldAtom)).toBeNull();
        expect(container!.querySelector('#title-editor-new-q-1')).not.toBeNull();
    }, 30_000);
});
