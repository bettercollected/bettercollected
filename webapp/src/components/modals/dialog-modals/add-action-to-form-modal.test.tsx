// The Google Sheets connect modal takes the consent popup's result only from
// the popup it opened, on the dashboard origin.
import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AddActionToFormModal from '@app/components/modals/dialog-modals/add-action-to-form-modal';
import { IntegrationType } from '@app/models/enums/integration-type';
import { apiActionsApi } from '@app/store/api-actions-api';
import { integrationApi } from '@app/store/integration-apis';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock('next/image', () => ({ default: () => null }));
vi.mock('@Components/modals/modal-wrapper/header-modal-wrapper', () => ({
    default: ({ headerTitle, children }: any) => (
        <div>
            <h2>{headerTitle}</h2>
            {children}
        </div>
    )
}));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ closeModal: vi.fn(), openModal: vi.fn() }) }));

const DASHBOARD = 'https://admin.example.test';
const SHEETS = { id: 'a-sheets', name: IntegrationType.GoogleSheet, title: 'Google Sheets', parameters: [{ name: 'Title', required: true }] };
const FORM = { formId: 'f1', title: 'Form', parameters: {} };

const requests: Array<{ url: string; body: string }> = [];
const frames: HTMLIFrameElement[] = [];

/** A window other than this one (a stand-in for a popup). */
const otherWindow = (): Window => {
    const frame = document.createElement('iframe');
    document.body.appendChild(frame);
    frames.push(frame);
    return frame.contentWindow!;
};

beforeEach(() => {
    requests.length = 0;
    window.PUBLIC_CONFIG = { HTTP_SCHEME: 'https://', DASHBOARD_DOMAIN: 'admin.example.test' } as any;
    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: any) => {
            const url = typeof input === 'string' ? input : input.url;
            const body = typeof input === 'string' ? '' : await input.clone().text();
            requests.push({ url, body });
            const answer = url.endsWith('/oauth/callback') ? 'Added credentials to form action' : url.includes('/oauth') ? 'https://accounts.google.com/o/oauth2/auth?x=1' : url.includes('/providers') ? [{ providerName: 'google', importMode: 'on' }] : {};
            return new Response(JSON.stringify(answer), { status: 200, headers: { 'Content-Type': 'application/json' } });
        })
    );
    store.dispatch(apiActionsApi.util.resetApiState());
    store.dispatch(integrationApi.util.resetApiState());
    store.dispatch(setWorkspace({ id: 'ws1', workspaceName: 'acme', title: 'Acme' } as any));
});

afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    frames.splice(0).forEach((frame) => frame.remove());
});

const callbacks = () => requests.filter((request) => request.url.endsWith('/oauth/callback'));

/** Open the modal and start the connection; returns the popup it opened. */
const startConnecting = async (): Promise<Window> => {
    const popup = otherWindow();
    const open = vi.spyOn(window, 'open').mockImplementation(() => popup as any);
    render(
        <ReduxProvider store={store}>
            <AddActionToFormModal action={SHEETS} form={FORM} />
        </ReduxProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: /Connect to Google/ }));
    await waitFor(() => expect(open).toHaveBeenCalled());
    return popup;
};

const post = async (origin: string, source: Window, data: unknown) => {
    await act(async () => {
        window.dispatchEvent(new MessageEvent('message', { data, origin, source }));
        await new Promise((resolve) => setTimeout(resolve, 50));
    });
};

describe('the Google Sheets connect modal', () => {
    it('ignores a message from another origin', async () => {
        const popup = await startConnecting();

        await post('https://elsewhere.example.test', popup, { code: 'c', state: 's' });

        expect(callbacks()).toHaveLength(0);
    });

    it('ignores a message on the dashboard origin from a window other than its popup', async () => {
        await startConnecting();

        await post(DASHBOARD, otherWindow(), { code: 'c', state: 's' });

        expect(callbacks()).toHaveLength(0);
    });

    it("completes the connection with its popup's code and state", async () => {
        const popup = await startConnecting();

        await post(DASHBOARD, popup, { code: 'the-code', state: 'the-state', extra: 'x' });

        await waitFor(() => expect(callbacks()).toHaveLength(1));
        expect(JSON.parse(callbacks()[0].body)).toEqual({ code: 'the-code', state: 'the-state', action_id: SHEETS.id, form_id: FORM.formId });
    });

    it("shows the popup's refusal", async () => {
        const popup = await startConnecting();

        await post(DASHBOARD, popup, { error: 'access_denied' });

        expect(await screen.findByText('Access has been denied')).toBeInTheDocument();
        expect(callbacks()).toHaveLength(0);
    });
});
