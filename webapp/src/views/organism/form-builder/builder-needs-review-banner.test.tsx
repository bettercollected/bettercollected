import React, { Suspense } from 'react';

import { act, render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import FormEditPage from '@app/app/(admin-portal)/(no-layout)/[workspace_name]/dashboard/forms/[form_id]/edit/_components/form-edit-page';
import { FieldTypes } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { openFormulierenImportApi } from '@app/store/redux/open-formulieren-import-api';
import { store as reduxStore } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

/**
 * An imported form that still needs review: the builder shows a strip that
 * links to the import report, and drops it once the report says reviewed.
 */

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/form-1/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));

const baseForm = {
    formId: 'form-1',
    title: 'Imported form',
    welcomePage: { title: 'Imported form' },
    thankyouPage: [{ id: 'ending-1', title: 'Thanks' }],
    fields: [{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [{ id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name' }] } }]
};
const marked = { needsReview: true, importSource: 'open_formulieren', importId: 'imp1' };

const reportAnswer = (needsReview: boolean) =>
    new Response(JSON.stringify({ id: 'imp1', formId: 'form-1', status: 'completed', needsReview, summary: { pages: 1, fields: 1, logicRules: 0, dropped: 0, flagged: 0 }, report: { truncated: false, items: [] } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
    });

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
    vi.unstubAllGlobals();
    reduxStore.dispatch(setForm({} as any));
    reduxStore.dispatch(openFormulierenImportApi.util.resetApiState());
});

async function openBuilder(settings: Record<string, unknown> | undefined) {
    reduxStore.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    reduxStore.dispatch(setForm({ ...structuredClone(baseForm), settings } as any));
    await act(async () => {
        render(
            <ReduxProvider store={reduxStore}>
                <Provider store={createStore()}>
                    <Suspense fallback={null}>
                        <FormEditPage params={Promise.resolve({ form_id: 'form-1' })} />
                    </Suspense>
                </Provider>
            </ReduxProvider>
        );
    });
    for (let i = 0; i < 5; i++) {
        await act(async () => {
            await vi.advanceTimersByTimeAsync(10);
        });
    }
}

describe('the builder of an imported form', () => {
    it('shows a strip that links to the import report', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => reportAnswer(true))
        );
        await openBuilder(marked);
        const banner = screen.getByText('This form was imported from Open Formulieren and needs review.').closest('[role="status"]') as HTMLElement;
        expect(banner).not.toBeNull();
        expect(screen.getByRole('link', { name: 'See the import report' })).toHaveAttribute('href', '/acme/dashboard/forms/import/open-formulieren/imp1');
    }, 30_000);

    it('drops the strip once the report says reviewed', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => reportAnswer(false))
        );
        await openBuilder(marked);
        expect(screen.queryByText('This form was imported from Open Formulieren and needs review.')).toBeNull();
    }, 30_000);

    it('shows no strip for a form that was not imported or is already reviewed', async () => {
        const fetchMock = vi.fn(async () => reportAnswer(true));
        vi.stubGlobal('fetch', fetchMock);
        await openBuilder({ needsReview: false, importSource: 'open_formulieren', importId: 'imp1' });
        expect(screen.queryByText('This form was imported from Open Formulieren and needs review.')).toBeNull();
        // no report is asked for
        expect(fetchMock.mock.calls.filter((call) => String((call as any[])[0]?.url ?? (call as any[])[0]).includes('open-formulieren-imports'))).toHaveLength(0);
    }, 30_000);
});
