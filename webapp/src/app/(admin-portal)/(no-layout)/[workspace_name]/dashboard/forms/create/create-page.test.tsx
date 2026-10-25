// The New Form page on a phone: Start with AI opens its dialog (which fits
// 375px) instead of doing nothing.
import React, { Suspense } from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import CreateFormPage from './page';

let isMobile = true;
vi.mock('@app/lib/hooks/use-breakpoint', () => ({ useIsMobile: () => isMobile }));
const openDialogModal = vi.fn();
vi.mock('@app/lib/hooks/use-dialog-modal', () => ({ useDialogModal: () => ({ openDialogModal }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => permission === WorkspacePermission.FORM_CREATE, ready: true, isLoading: false })
}));
const openModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal }) }));
vi.mock('next-nprogress-bar', () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));
vi.mock('@fyelci/react-google-drive-picker', () => ({ default: () => [vi.fn()] }));
vi.mock('@app/components/pdf-import/import-pdf-dialog', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/navbar', () => ({ default: () => null }));
vi.mock('@app/store/redux/template-api', async (importOriginal) => ({
    ...((await importOriginal()) as object),
    useGetTemplatesQuery: () => ({ data: [] }),
    useCreateFormFromTemplateMutation: () => [vi.fn()]
}));

// what GET /providers reports (the Google Forms import switch)
const providers: { data: any; isLoading: boolean } = { data: [{ providerName: 'google', importMode: 'on' }], isLoading: false };
vi.mock('@app/store/redux/import-api', async (importOriginal) => ({
    ...((await importOriginal()) as object),
    useGetProvidersQuery: () => providers
}));

async function renderPage(searchParams: Record<string, string> = {}) {
    await act(async () => {
        render(
            <ReduxProvider store={store}>
                <Suspense fallback={null}>
                    <CreateFormPage searchParams={Promise.resolve(searchParams)} />
                </Suspense>
            </ReduxProvider>
        );
    });
}

const card = (name: string) => screen.getByText(name).parentElement as HTMLElement;

describe('the New Form page', () => {
    beforeEach(() => {
        openDialogModal.mockClear();
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    });

    it('on a phone, Start with AI opens its dialog and is not marked desktop-only', async () => {
        isMobile = true;
        await renderPage();
        expect(within(card('Start with AI')).queryByText('Only available on desktop')).toBeNull();
        fireEvent.click(card('Start with AI'));
        expect(openDialogModal).toHaveBeenCalledWith('START_WITH_AI');
        // creating a blank form in the builder stays desktop-only
        expect(within(card('Create New Form')).getByText('Only available on desktop')).toBeTruthy();
    });

    it('on a desktop, Start with AI opens its dialog', async () => {
        isMobile = false;
        await renderPage();
        fireEvent.click(card('Start with AI'));
        expect(openDialogModal).toHaveBeenCalledWith('START_WITH_AI');
    });
});

describe('the New Form page and the Google Forms import switch', () => {
    beforeEach(() => {
        isMobile = false;
        providers.isLoading = false;
        openModal.mockClear();
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    });

    it('offers the Google import while imports are on, or when the mode is unknown', async () => {
        providers.data = [{ providerName: 'google', importMode: 'on' }];
        await renderPage();
        expect(screen.getByText('Import Google Form')).toBeTruthy();
    });

    it('drops the Google import and says why when imports are read-only', async () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        await renderPage();
        expect(screen.queryByText('Import Google Form')).toBeNull();
        expect(screen.getByText('GOOGLE_FORMS_IMPORT.READONLY.CREATE_PAGE')).toBeTruthy();
        expect(screen.getByText('Import a PDF form')).toBeTruthy();
    });

    it('does not offer Google at all when imports are off', async () => {
        providers.data = [];
        await renderPage();
        expect(screen.queryByText('Import Google Form')).toBeNull();
        expect(screen.queryByText('GOOGLE_FORMS_IMPORT.READONLY.CREATE_PAGE')).toBeNull();
    });

    it('waits for the mode before offering the Google import', async () => {
        providers.data = undefined;
        providers.isLoading = true;
        await renderPage();
        expect(screen.queryByText('Import Google Form')).toBeNull();
    });

    it('offers the Google import as before when the mode list could not be read', async () => {
        providers.data = undefined;
        await renderPage();
        expect(screen.getByText('Import Google Form')).toBeTruthy();
        expect(screen.queryByText('GOOGLE_FORMS_IMPORT.READONLY.CREATE_PAGE')).toBeNull();
    });

    it('opens the import for ?modal=true while imports are on', async () => {
        providers.data = [{ providerName: 'google', importMode: 'on' }];
        await renderPage({ modal: 'true' });
        expect(openModal).toHaveBeenCalledWith('IMPORT_FORMS', { nonClosable: true });
    });

    it('does not open the import for ?modal=true when imports are read-only', async () => {
        providers.data = [{ providerName: 'google', importMode: 'readonly' }];
        await renderPage({ modal: 'true' });
        expect(openModal).not.toHaveBeenCalled();
        expect(screen.getByText('GOOGLE_FORMS_IMPORT.READONLY.CREATE_PAGE')).toBeTruthy();
    });

    it('does not open the import for ?modal=true when imports are off', async () => {
        providers.data = [];
        await renderPage({ modal: 'true' });
        expect(openModal).not.toHaveBeenCalled();
    });

    it('waits for the mode before opening the import for ?modal=true', async () => {
        providers.data = undefined;
        providers.isLoading = true;
        await renderPage({ modal: 'true' });
        expect(openModal).not.toHaveBeenCalled();
    });
});
