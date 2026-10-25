import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import FormIntegrations from '@app/components/form/integrations';
import AddActionToFormModal from '@app/components/modals/dialog-modals/add-action-to-form-modal';
import { sheetsReconnect } from '@app/constants/locales/sheets-reconnect';
import { IntegrationType } from '@app/models/enums/integration-type';
import { apiActionsApi } from '@app/store/api-actions-api';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import en from '../../../public/locales/en/common.json';
import nl from '../../../public/locales/nl/common.json';

const openModal = vi.fn();
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
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ closeModal: vi.fn(), openModal }) }));

const SHEETS = { id: 'a-sheets', name: IntegrationType.GoogleSheet, title: 'Google Sheets', description: 'Send responses to a sheet', parameters: [{ name: 'Title', required: true }] };
const MAIL = { id: 'a-mail', name: 'creator_copy_mail', title: 'Copy mail', description: 'Mail a copy', parameters: [] };
const FORM = {
    formId: 'f1',
    title: 'Form',
    actions: {
        on_submit: [
            { id: SHEETS.id, enabled: true },
            { id: MAIL.id, enabled: true }
        ]
    },
    parameters: { [SHEETS.id]: [{ name: 'Title', value: 'Responses 2026' }] }
};

let needsReconsent = false;
const requested: string[] = [];

function respond(url: string): unknown {
    if (url.endsWith('/reconsent')) return { needs_reconsent: needsReconsent };
    if (url.includes('/integration/integrate_google_sheets/oauth')) return 'https://accounts.google.com/o/oauth2/auth?x=1';
    if (url.includes('/providers')) return [{ providerName: 'google', importMode: 'on' }];
    if (/\/actions(\?|$)/.test(url)) return [SHEETS, MAIL];
    return {};
}

beforeEach(() => {
    needsReconsent = false;
    requested.length = 0;
    openModal.mockReset();
    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: any) => {
            const url = typeof input === 'string' ? input : input.url;
            requested.push(url);
            return new Response(JSON.stringify(respond(url)), { status: 200, headers: { 'Content-Type': 'application/json' } });
        })
    );
    store.dispatch(apiActionsApi.util.resetApiState());
    store.dispatch(setWorkspace({ id: 'ws1', workspaceName: 'acme', title: 'Acme' } as any));
    store.dispatch(setForm(FORM as any));
});

afterEach(() => {
    vi.unstubAllGlobals();
});

const renderList = () =>
    render(
        <ReduxProvider store={store}>
            <main>
                <FormIntegrations />
            </main>
        </ReduxProvider>
    );

describe('Google Sheets reconnect notice in the form actions list', () => {
    it('asks the builder endpoint for the Sheets action only', async () => {
        renderList();
        await screen.findByText('Google Sheets');
        await waitFor(() => expect(requested.some((url) => url.endsWith('/workspaces/ws1/forms/f1/actions/a-sheets/reconsent'))).toBe(true));
        expect(requested.filter((url) => url.endsWith('/reconsent'))).toHaveLength(1);
    });

    it('shows nothing when no reconnect is needed', async () => {
        renderList();
        await screen.findByText('Google Sheets');
        await waitFor(() => expect(requested.some((url) => url.endsWith('/reconsent'))).toBe(true));
        expect(screen.queryByText(sheetsReconnect.title)).toBeNull();
        expect(screen.queryByText(sheetsReconnect.badge)).toBeNull();
        expect(screen.queryByRole('button', { name: sheetsReconnect.button })).toBeNull();
    });

    it('marks the action and explains, with a status role, when a reconnect is needed', async () => {
        needsReconsent = true;
        renderList();
        const status = await screen.findByRole('status');
        expect(status.textContent).toContain(sheetsReconnect.title);
        expect(status.textContent).toContain(sheetsReconnect.description);
        const notice = screen.getByRole('region', { name: sheetsReconnect.title });
        const badge = screen.getByText(sheetsReconnect.badge);
        // The new parts only: the card's switch and menu predate this notice.
        expect(await axeViolations(notice)).toEqual([]);
        expect(await axeViolations(badge.parentElement!)).toEqual([]);
    });

    it('starts the existing connect flow from the button', async () => {
        needsReconsent = true;
        renderList();
        const button = await screen.findByRole('button', { name: sheetsReconnect.button });
        button.focus();
        expect(button).toHaveFocus();
        fireEvent.click(button);
        expect(openModal).toHaveBeenCalledWith('ADD_ACTION_TO_FORM', expect.objectContaining({ action: expect.objectContaining({ id: SHEETS.id }), reconnect: true }));
    });
});

describe('the connect flow opened to reconnect', () => {
    it('is titled as a reconnect and asks Google for a new grant', async () => {
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        render(
            <ReduxProvider store={store}>
                <AddActionToFormModal action={SHEETS} form={FORM} reconnect />
            </ReduxProvider>
        );
        expect(await screen.findByRole('heading', { name: sheetsReconnect.button })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /Connect to Google/ }));
        await waitFor(() => expect(open).toHaveBeenCalledWith('https://accounts.google.com/o/oauth2/auth?x=1', 'oauthWindow', expect.any(String)));
        expect(requested.some((url) => url.endsWith('/integration/integrate_google_sheets/oauth'))).toBe(true);
        open.mockRestore();
    });
});

describe('reconnect strings', () => {
    const keys = Object.values(sheetsReconnect).map((key) => key.split('.')[1]);

    it('exist in English and Dutch', () => {
        for (const key of keys) {
            expect((en as any).SHEETS_RECONNECT[key]).toBeTruthy();
            expect((nl as any).SHEETS_RECONNECT[key]).toBeTruthy();
            expect((nl as any).SHEETS_RECONNECT[key]).not.toBe((en as any).SHEETS_RECONNECT[key]);
        }
        expect((en as any).SHEETS_RECONNECT.BUTTON).toBe('Reconnect Google Sheets');
        expect((nl as any).SHEETS_RECONNECT.BUTTON).toBe('Google Sheets opnieuw koppelen');
    });
});
