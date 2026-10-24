import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AddActionToFormModal from '@app/components/modals/dialog-modals/add-action-to-form-modal';
import { IntegrationType } from '@app/models/enums/integration-type';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import WorkspaceDashboardForms, { isGoogleForm } from './workspace-dashboard-forms';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock('@app/components/workspace-dashboard/workspace-dashboard-form-cards', () => ({ default: () => <p>form cards</p> }));
vi.mock('@app/views/atoms/new-form-button', () => ({ default: () => <button>New form</button> }));
vi.mock('@Components/modals/modal-wrapper/header-modal-wrapper', () => ({ default: ({ children }: any) => <div>{children}</div> }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ closeModal: vi.fn(), openModal: vi.fn() }) }));
vi.mock('next/image', () => ({ default: () => null }));

const providers: { data: any } = { data: undefined };
vi.mock('@app/store/redux/import-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetProvidersQuery: () => ({ data: providers.data, isLoading: false }) };
});

const forms: { items: any[] } = { items: [] };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceFormsQuery: () => ({ isLoading: false, data: { items: forms.items, total: forms.items.length, pages: 1 } }),
        useLazySearchWorkspaceFormsQuery: () => [vi.fn()]
    };
});

const fetchOauthUrl = vi.fn();
vi.mock('@app/store/integration-apis', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useLazyGetIntegrationOauthUrlQuery: () => [fetchOauthUrl, {}],
        useHandleIntegrationOauthCallbackMutation: () => [vi.fn()]
    };
});

const GOOGLE_FORM = { formId: 'g1', title: 'Imported', settings: { provider: 'google' } };
const NATIVE_FORM = { formId: 'n1', title: 'Ours', settings: { provider: 'self' } };

const renderList = () =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceDashboardForms workspace={{ id: 'ws1' } as any} hasCustomDomain={false} showPagination />
        </ReduxProvider>
    );

describe('forms list and the Google Forms import switch', () => {
    beforeEach(() => {
        store.dispatch(setWorkspace({ id: 'ws1', workspaceName: 'acme', title: 'Acme' } as any));
    });

    it('recognises imported Google forms', () => {
        expect(isGoogleForm(GOOGLE_FORM as any)).toBe(true);
        expect(isGoogleForm({ settings: { provider: 'self' }, importedFormId: 'x' } as any)).toBe(true);
        expect(isGoogleForm(NATIVE_FORM as any)).toBe(false);
    });

    it('explains read-only imports next to imported Google forms', () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        forms.items = [NATIVE_FORM, GOOGLE_FORM];
        renderList();
        expect(screen.getByRole('note').textContent).toContain('GOOGLE_FORMS_IMPORT.READONLY.TITLE');
    });

    it('explains turned-off imports next to imported Google forms', () => {
        providers.data = [];
        forms.items = [GOOGLE_FORM];
        renderList();
        expect(screen.getByRole('note').textContent).toContain('GOOGLE_FORMS_IMPORT.OFF.TITLE');
    });

    it('says nothing without Google forms, or while imports are on', () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        forms.items = [NATIVE_FORM];
        renderList();
        expect(screen.queryByRole('note')).toBeNull();

        providers.data = [{ providerName: 'google', importMode: 'on' }];
        forms.items = [GOOGLE_FORM];
        renderList();
        expect(screen.queryByRole('note')).toBeNull();
    });
});

describe('Google Sheets action and the Google Forms import switch', () => {
    const SHEETS = { id: 'a1', name: IntegrationType.GoogleSheet, title: 'Google Sheets' };
    const renderSheets = () =>
        render(
            <ReduxProvider store={store}>
                <AddActionToFormModal action={SHEETS} form={{ formId: 'f1', title: 'Form' }} />
            </ReduxProvider>
        );

    beforeEach(() => fetchOauthUrl.mockReset());

    it('explains why Google Sheets cannot be connected when imports are off', () => {
        providers.data = [];
        renderSheets();
        expect(screen.getByRole('note').textContent).toBe('GOOGLE_FORMS_IMPORT.OFF.SHEETS');
        expect(screen.queryByRole('button', { name: /Connect to Google/ })).toBeNull();
    });

    it('still connects Google Sheets in read-only mode, and explains a 410', async () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        fetchOauthUrl.mockResolvedValue({ error: { status: 410, data: { code: 'google_forms_off' } } });
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        renderSheets();

        fireEvent.click(screen.getByRole('button', { name: /Connect to Google/ }));
        await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('GOOGLE_FORMS_IMPORT.OFF.SHEETS'));
        expect(open).not.toHaveBeenCalled();
        open.mockRestore();
    });
});
