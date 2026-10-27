import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { setForm } from '@app/store/forms/slice';
import { openFormulierenImportApi } from '@app/store/redux/open-formulieren-import-api';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import Navbar from './navbar';

const createTemplateMock = vi.fn();
const toastMock = vi.fn();
vi.mock('@app/store/redux/template-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useCreateTemplateFromFormMutation: () => [createTemplateMock, { isLoading: false }] };
});
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/ws/dashboard/forms/form-1/edit' }));
vi.mock('next/dynamic', () => ({ default: () => () => null }));
vi.mock('../molecules/form-builder/publish-button', () => ({ default: () => null }));
vi.mock('../molecules/form-builder/preview-wrapper', () => ({ default: () => null }));
vi.mock('../molecules/form-builder/keyboard-shortcuts', () => ({ default: () => null }));
vi.mock('../molecules/dialogs/insert-field-modal', () => ({ default: () => null }));
vi.mock('./form/form', () => ({ default: () => null }));

const MARKED = { needsReview: true, importSource: 'open_formulieren', importId: 'imp1' };
const REPORT = { id: 'imp1', formId: 'form-1', status: 'completed', needsReview: true, summary: { pages: 1, fields: 1, logicRules: 0, dropped: 0, flagged: 0 }, report: { truncated: false, items: [] } };
const REFUSAL = { error: { status: 422, data: { code: 'needs_review', message: 'x', problems: [{ code: 'needs_review', fieldId: null, importId: 'imp9', message: 'It was imported and still needs review.' }] } } };

function json(status: number, body: unknown) {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

/** The server's answer to a review call and to reading the report. */
function stubApi(state: { needsReview: boolean }) {
    const calls: Array<{ url: string; method: string; body?: string }> = [];
    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: any, init?: any) => {
            const request = input instanceof Request ? input : null;
            const url = request ? request.url : String(input);
            const method = request ? request.method : (init?.method ?? 'GET');
            const body = request ? await request.clone().text() : init?.body;
            calls.push({ url, method, body });
            if (method === 'POST') state.needsReview = !JSON.parse(body as string).reviewed;
            return json(200, { ...REPORT, needsReview: state.needsReview });
        })
    );
    return calls;
}

const setUp = (settings: Record<string, unknown>) => {
    store.dispatch(setAuth({ roles: ['ADMIN'] }));
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(setForm({ formId: 'form-1', title: 'Imported form', settings } as any));
};

async function renderNavbar() {
    await act(async () => {
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Navbar />
                </Provider>
            </ReduxProvider>
        );
    });
}

const makeTemplate = () => screen.getByRole('button', { name: 'Make Template' });

describe('making a template from a form that still needs review', () => {
    beforeEach(() => {
        createTemplateMock.mockReset().mockResolvedValue({ data: { id: 't1' } });
        toastMock.mockReset();
        store.dispatch(openFormulierenImportApi.util.resetApiState());
    });
    afterEach(async () => {
        vi.unstubAllGlobals();
        await i18n.changeLanguage('en');
    });

    it('the click opens the explanation, with the report, instead of asking the server', async () => {
        stubApi({ needsReview: true });
        setUp(MARKED);
        await renderNavbar();
        await waitFor(() => expect(makeTemplate()).toBeInTheDocument());
        await act(async () => {
            fireEvent.click(makeTemplate());
        });
        const dialog = await screen.findByRole('dialog', { name: 'This form still needs review' });
        expect(dialog).toHaveTextContent('A template can be made once you have marked it as reviewed');
        expect(await screen.findByRole('link', { name: 'Open the import report' })).toHaveAttribute('href', '/acme/dashboard/forms/import/open-formulieren/imp1');
        expect(createTemplateMock).not.toHaveBeenCalled();
    });

    it('marking it as reviewed in the dialog makes the template at once', async () => {
        const calls = stubApi({ needsReview: true });
        setUp(MARKED);
        await renderNavbar();
        await act(async () => {
            fireEvent.click(makeTemplate());
        });
        await act(async () => {
            fireEvent.click(await screen.findByRole('button', { name: 'Mark as reviewed' }));
        });
        expect(calls.some((call) => call.method === 'POST' && call.url.endsWith('/workspaces/ws-1/open-formulieren-imports/imp1/review') && JSON.parse(call.body as string).reviewed === true)).toBe(true);
        await waitFor(() => expect(createTemplateMock).toHaveBeenCalledWith({ form_id: 'form-1', workspace_id: 'ws-1' }));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: 'Temaplate Created' })));
        expect(screen.queryByRole('dialog', { name: 'This form still needs review' })).not.toBeInTheDocument();
    });

    it("the server's refusal opens the same explanation, with the report it names", async () => {
        stubApi({ needsReview: true });
        createTemplateMock.mockResolvedValue(REFUSAL);
        // the form carries no mark here (a stale copy): only the server knows
        setUp({});
        await renderNavbar();
        await act(async () => {
            fireEvent.click(makeTemplate());
        });
        expect(await screen.findByRole('dialog', { name: 'This form still needs review' })).toBeInTheDocument();
        expect(await screen.findByRole('link', { name: 'Open the import report' })).toHaveAttribute('href', '/acme/dashboard/forms/import/open-formulieren/imp9');
        expect(toastMock).not.toHaveBeenCalled();
    });

    it('is never silent when the server names no import: the explanation shows, nothing to clear', async () => {
        stubApi({ needsReview: true });
        createTemplateMock.mockResolvedValue({ error: { status: 422, data: { code: 'needs_review', message: 'x', problems: [{ code: 'needs_review', fieldId: null, importId: null, message: 'm' }] } } });
        setUp({});
        await renderNavbar();
        await act(async () => {
            fireEvent.click(makeTemplate());
        });
        expect(await screen.findByRole('dialog', { name: 'This form still needs review' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Mark as reviewed' })).not.toBeInTheDocument();
        expect(screen.getAllByRole('button', { name: 'Close' }).length).toBeGreaterThan(0);
    });

    it('a form that is not marked becomes a template as before', async () => {
        setUp({});
        await renderNavbar();
        await act(async () => {
            fireEvent.click(makeTemplate());
        });
        await waitFor(() => expect(createTemplateMock).toHaveBeenCalledTimes(1));
        expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: 'Temaplate Created' }));
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('any other failure says so instead of staying silent', async () => {
        setUp({});
        createTemplateMock.mockResolvedValue({ error: { status: 500, data: {} } });
        await renderNavbar();
        await act(async () => {
            fireEvent.click(makeTemplate());
        });
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ variant: 'destructive' })));
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('speaks Dutch with the Dutch register', async () => {
        stubApi({ needsReview: true });
        await i18n.changeLanguage('nl');
        setUp(MARKED);
        await renderNavbar();
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Make Template' }));
        });
        const dialog = await screen.findByRole('dialog', { name: 'Dit formulier moet nog worden nagekeken' });
        expect(dialog).toHaveTextContent('Er kan pas een sjabloon van worden gemaakt');
    });
});
