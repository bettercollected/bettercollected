// The New Form page and the Open Formulieren import switch: the card is offered
// only when GET /providers lists open_formulieren. (Own file: it loads the real
// translations, which the other create-page tests do not.)
import React, { Suspense } from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import CreateFormPage from './page';

let isMobile = false;
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

async function renderPage() {
    let result: ReturnType<typeof render> | undefined;
    await act(async () => {
        result = render(
            <ReduxProvider store={store}>
                <Suspense fallback={null}>
                    <CreateFormPage searchParams={Promise.resolve({})} />
                </Suspense>
            </ReduxProvider>
        );
    });
    return result as ReturnType<typeof render>;
}

describe('the New Form page and the Open Formulieren import switch', () => {
    beforeEach(() => {
        providers.isLoading = false;
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme' } as any));
    });

    it('offers the card next to the PDF import when /providers lists open_formulieren', async () => {
        providers.data = [
            { providerName: 'google', importMode: 'on' },
            { providerName: 'open_formulieren', importMode: 'on' }
        ];
        await renderPage();
        expect(screen.getByText('Import a PDF form')).toBeTruthy();
        expect(screen.getByText('Import from Open Formulieren')).toBeTruthy();
    });

    it('hides the card without the providers entry, on an unknown mode and on an unreadable list', async () => {
        for (const data of [[{ providerName: 'google', importMode: 'on' }], [], [{ providerName: 'open_formulieren', importMode: 'readonly' }], [{ providerName: 'open_formulieren' }], undefined]) {
            providers.data = data;
            const { unmount } = await renderPage();
            expect(screen.queryByText('Import from Open Formulieren')).toBeNull();
            expect(screen.getByText('Import a PDF form')).toBeTruthy();
            unmount();
        }
    });

    it('hides the card while the provider list loads', async () => {
        providers.data = undefined;
        providers.isLoading = true;
        await renderPage();
        expect(screen.queryByText('Import from Open Formulieren')).toBeNull();
    });

    it('opens the upload dialog from the card, with the keyboard too', async () => {
        providers.data = [{ providerName: 'open_formulieren', importMode: 'on' }];
        await renderPage();
        expect(screen.queryByRole('dialog')).toBeNull();
        const card = screen.getByText('Import from Open Formulieren').parentElement as HTMLElement;
        expect(card).toHaveAttribute('role', 'button');
        expect(card).toHaveAttribute('tabindex', '0');
        fireEvent.keyDown(card, { key: 'Enter' });
        expect(await screen.findByRole('dialog')).toHaveTextContent('One form per zip file, up to 5 MB');
    });
});
