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
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));
vi.mock('next-nprogress-bar', () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));
vi.mock('@fyelci/react-google-drive-picker', () => ({ default: () => [vi.fn()] }));
vi.mock('@app/components/pdf-import/import-pdf-dialog', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/navbar', () => ({ default: () => null }));
vi.mock('@app/store/redux/template-api', async (importOriginal) => ({
    ...((await importOriginal()) as object),
    useGetTemplatesQuery: () => ({ data: [] }),
    useCreateFormFromTemplateMutation: () => [vi.fn()]
}));

async function renderPage() {
    await act(async () => {
        render(
            <ReduxProvider store={store}>
                <Suspense fallback={null}>
                    <CreateFormPage searchParams={Promise.resolve({})} />
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
