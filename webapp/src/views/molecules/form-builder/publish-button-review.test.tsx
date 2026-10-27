import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { openFormulierenImportApi } from '@app/store/redux/open-formulieren-import-api';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import PublishButton from './publish-button';

const publishFormMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, usePublishV2FormMutation: () => [publishFormMock, { isLoading: false }] };
});
vi.mock('@app/lib/hooks/use-dialog-modal', () => ({ useDialogModal: () => ({ openDialogModal: vi.fn() }) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/ws/dashboard/forms/form-1/edit' }));
vi.mock('@app/views/molecules/form-builder/audo-save-form', () => ({ flushAutosave: async () => 'saved' }));

const MARKED = { needsReview: true, importSource: 'open_formulieren', importId: 'imp1' };
const REPORT = { id: 'imp1', formId: 'form-1', status: 'completed', needsReview: true, summary: { pages: 1, fields: 1, logicRules: 0, dropped: 0, flagged: 0 }, report: { truncated: false, items: [] } };
const PAGE = [{ id: 'page-1', index: 0, type: 'slide', properties: { fields: [{ id: 'q-1', index: 0, type: 'short_text', title: 'Name', description: '' }] } }];

function json(status: number, body: unknown) {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

/** The server's answer to a review call, and to reading the report. */
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

function renderButton() {
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <PublishButton fields={PAGE as any} />
            </Provider>
        </ReduxProvider>
    );
}

const setUp = (settings: Record<string, unknown>) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    store.dispatch(setForm({ formId: 'form-1', title: 'Imported form', settings, thankyouPage: [{ id: 'end-1', name: 'Thanks' }] } as any));
};

describe('publishing a form that still needs review', () => {
    beforeEach(() => {
        publishFormMock.mockReset().mockResolvedValue({ data: { formId: 'form-1' } });
        store.dispatch(openFormulierenImportApi.util.resetApiState());
    });
    afterEach(async () => {
        vi.unstubAllGlobals();
        await i18n.changeLanguage('en');
    });

    it('says why on the button, and the click opens the explanation instead of publishing', async () => {
        stubApi({ needsReview: true });
        setUp(MARKED);
        await act(async () => {
            renderButton();
        });
        await waitFor(() => expect(screen.getByRole('button', { name: 'Publish' })).toHaveAttribute('title', 'Publishing waits until the import is marked as reviewed.'));
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        });
        const dialog = await screen.findByRole('dialog', { name: 'This form still needs review' });
        expect(dialog).toHaveTextContent('Publishing waits until you have looked through the import report and marked it as reviewed.');
        expect(screen.getByRole('link', { name: 'Open the import report' })).toHaveAttribute('href', '/acme/dashboard/forms/import/open-formulieren/imp1');
        expect(publishFormMock).not.toHaveBeenCalled();
    });

    it('clearing the mark in the dialog makes publishing work', async () => {
        const calls = stubApi({ needsReview: true });
        setUp(MARKED);
        await act(async () => {
            renderButton();
        });
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        });
        await act(async () => {
            fireEvent.click(await screen.findByRole('button', { name: 'Mark as reviewed' }));
        });
        expect(calls.some((call) => call.method === 'POST' && call.url.endsWith('/workspaces/ws-1/open-formulieren-imports/imp1/review') && JSON.parse(call.body as string).reviewed === true)).toBe(true);
        expect(await screen.findByText('Marked as reviewed. You can publish now.')).toBeInTheDocument();
        expect(publishFormMock).not.toHaveBeenCalled();
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Publish now' }));
        });
        await waitFor(() => expect(publishFormMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'form-1' }));
        expect(screen.queryByRole('dialog', { name: 'This form still needs review' })).not.toBeInTheDocument();
    });

    it('a form whose report was already marked reviewed publishes at once', async () => {
        stubApi({ needsReview: false });
        setUp(MARKED);
        await act(async () => {
            renderButton();
        });
        await waitFor(() => expect(screen.getByRole('button', { name: 'Publish' })).not.toHaveAttribute('title'));
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        });
        await waitFor(() => expect(publishFormMock).toHaveBeenCalledTimes(1));
    });

    it("the server's refusal opens the same explanation, with the report it names", async () => {
        stubApi({ needsReview: true });
        publishFormMock.mockResolvedValue({ error: { status: 422, data: { code: 'form_not_publishable', message: 'x', problems: [{ code: 'needs_review', fieldId: null, importId: 'imp9', message: 'It was imported and still needs review.' }] } } });
        // the form carries no mark here (a stale copy): only the server knows
        setUp({});
        await act(async () => {
            renderButton();
        });
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        });
        expect(await screen.findByRole('dialog', { name: 'This form still needs review' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Open the import report' })).toHaveAttribute('href', '/acme/dashboard/forms/import/open-formulieren/imp9');
        expect(screen.queryByText('Before you publish')).not.toBeInTheDocument();
    });

    it('a form that is not an import publishes as before', async () => {
        stubApi({ needsReview: false });
        setUp({});
        await act(async () => {
            renderButton();
        });
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        });
        await waitFor(() => expect(publishFormMock).toHaveBeenCalledTimes(1));
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('speaks Dutch, in the "u" register', async () => {
        await i18n.changeLanguage('nl');
        stubApi({ needsReview: true });
        setUp(MARKED);
        await act(async () => {
            renderButton();
        });
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Publish' }));
        });
        const dialog = await screen.findByRole('dialog', { name: 'Dit formulier moet nog worden nagekeken' });
        expect(dialog).toHaveTextContent('U kunt pas publiceren nadat u het importrapport hebt doorgenomen');
        expect(screen.getByRole('link', { name: 'Open het importrapport' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Markeer als nagekeken' })).toBeInTheDocument();
    });
});
