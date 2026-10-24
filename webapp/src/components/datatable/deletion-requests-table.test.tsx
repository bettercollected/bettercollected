import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CloseDeletionRequestModal from '@app/components/modal-views/modals/close-deletion-request-modal';
import { closeDeletionRequestError, isDeclineReason, isDeclinedRequest, isPendingRequest } from '@app/models/enums/deletion-request';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { statusProps } from '@app/utils/vvalidation-utils';

import ResponsesTable from './responses-table';

const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));

const openModal = vi.fn();
const closeModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal, closeModal }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@Components/modals/modal-wrapper/header-modal-wrapper', () => ({ default: ({ children }: any) => <div>{children}</div> }));

const toast = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));

const closeRequest = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useLazyGetWorkspaceSubmissionQuery: () => [vi.fn()],
        useCloseDeletionRequestMutation: () => [closeRequest, { isLoading: false }]
    };
});

// react-data-table-component reads the colour scheme
if (!window.matchMedia) {
    window.matchMedia = ((query: string) => ({ matches: false, media: query, onchange: null, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false })) as any;
}

const request = (id: string, extra: Record<string, unknown> = {}) => ({
    responseId: id,
    formId: 'form-g',
    formTitle: 'Imported form',
    provider: 'google',
    formImportedBy: 'someone-else',
    dataOwnerIdentifier: `${id}@example.com`,
    createdAt: '2026-10-01T10:00:00Z',
    updatedAt: '2026-10-02T10:00:00Z',
    status: 'pending',
    ...extra
});
const page = (items: any[]) => ({ items, total: items.length, page: 1, size: 50, pages: 1 }) as any;

const renderTable = (items: any[]) =>
    render(
        <ReduxProvider store={store}>
            <ResponsesTable requestForDeletion={true} page={1} setPage={vi.fn()} submissions={page(items)} />
        </ReduxProvider>
    );

const rowOf = (email: string) => screen.getByText(email).closest('[role="row"]') as HTMLElement;

const WORKSPACE = { id: 'ws1', workspaceName: 'acme', title: 'Acme' } as any;

describe('deletion request helpers', () => {
    it('reads statuses, reasons and the close errors', () => {
        expect(isPendingRequest(undefined)).toBe(true);
        expect(isPendingRequest('Pending')).toBe(true);
        expect(isPendingRequest('declined')).toBe(false);
        expect(isDeclinedRequest('declined')).toBe(true);
        expect(isDeclinedRequest('success')).toBe(false);
        expect(isDeclineReason('legal_claims')).toBe(true);
        expect(isDeclineReason('because')).toBe(false);
        expect(closeDeletionRequestError({ status: 409, data: { code: 'deletion_request_closed' } })).toBe('alreadyClosed');
        expect(closeDeletionRequestError({ status: 409, data: { code: 'deletion_request_copy_unresolved' } })).toBe('copyUnresolved');
        expect(closeDeletionRequestError({ status: 403, data: 'Forbidden' })).toBe('failed');
    });

    it('never words a declined request as deleted', () => {
        const t = (key: string) => key;
        expect(statusProps('declined', t).currentStatus).toBe('FORM.STATUS_DECLINED');
        expect(statusProps('success', t).currentStatus).toBe('FORM.STATUS_DELETED');
    });
});

describe('deletion requests of imported forms', () => {
    beforeEach(() => {
        openModal.mockReset();
        store.dispatch(setWorkspace(WORKSPACE));
        store.dispatch(setAuth({ id: 'me', email: 'me@example.com', roles: [] } as any));
    });

    it('lets privacy staff mark a pending request deleted or decline it', () => {
        access.permissions = ['privacy.manage'];
        renderTable([request('r1')]);

        const row = rowOf('r1@example.com');
        fireEvent.click(within(row).getByRole('button', { name: 'DELETION_REQUEST.MARK_DELETED' }));
        expect(openModal).toHaveBeenLastCalledWith('CLOSE_DELETION_REQUEST', { workspace: expect.objectContaining({ id: 'ws1' }), formId: 'form-g', responseId: 'r1', outcome: 'completed' });
        fireEvent.click(within(row).getByRole('button', { name: 'DELETION_REQUEST.DECLINE' }));
        expect(openModal).toHaveBeenLastCalledWith('CLOSE_DELETION_REQUEST', expect.objectContaining({ responseId: 'r1', outcome: 'declined' }));
    });

    it('offers nothing to close without privacy.manage', () => {
        access.permissions = ['response.read'];
        renderTable([request('r1')]);
        expect(screen.queryByRole('button', { name: 'DELETION_REQUEST.MARK_DELETED' })).toBeNull();
        expect(screen.queryByRole('button', { name: 'DELETION_REQUEST.DECLINE' })).toBeNull();
    });

    it('shows a declined request with its reason and never as deleted', () => {
        access.permissions = ['privacy.manage'];
        renderTable([request('r2', { status: 'declined', declineReason: 'legal_obligation' }), request('r3', { status: 'success' })]);

        const declined = rowOf('r2@example.com');
        expect(within(declined).getByText('DELETION_REQUEST.REASON.LEGAL_OBLIGATION')).toBeTruthy();
        expect(within(declined).getByText('DELETION_REQUEST.NOT_DELETED')).toBeTruthy();
        expect(within(declined).queryByText(/STATUS_DELETED|Deleted/)).toBeNull();
        expect(within(declined).queryByRole('button')).toBeNull();

        const deleted = rowOf('r3@example.com');
        expect(within(deleted).queryByText('DELETION_REQUEST.NOT_DELETED')).toBeNull();
        expect(within(deleted).queryByRole('button')).toBeNull();
    });

    it('treats an unknown decline reason as "another reason"', () => {
        access.permissions = ['privacy.manage'];
        renderTable([request('r4', { status: 'declined', declineReason: 'made_up' })]);
        expect(within(rowOf('r4@example.com')).getByText('DELETION_REQUEST.REASON.OTHER')).toBeTruthy();
    });
});

describe('CloseDeletionRequestModal', () => {
    beforeEach(() => {
        closeRequest.mockReset();
        closeModal.mockReset();
        toast.mockReset();
    });

    const renderModal = (outcome: 'completed' | 'declined') =>
        render(
            <ReduxProvider store={store}>
                <CloseDeletionRequestModal workspace={WORKSPACE} formId="form-g" responseId="r1" outcome={outcome} />
            </ReduxProvider>
        );

    it('marks a request deleted', async () => {
        closeRequest.mockResolvedValue({ data: { status: 'success' } });
        renderModal('completed');
        fireEvent.click(screen.getAllByRole('button', { name: 'DELETION_REQUEST.MARK_DELETED' }).at(-1)!);

        await waitFor(() => expect(closeRequest).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'form-g', responseId: 'r1', outcome: 'completed' }));
        expect(closeModal).toHaveBeenCalled();
        expect(toast).toHaveBeenCalledWith({ description: 'DELETION_REQUEST.MARKED_DELETED' });
    });

    it('needs a reason to decline, and sends only the code', async () => {
        closeRequest.mockResolvedValue({ data: { status: 'declined', declineReason: 'identity_not_verified' } });
        renderModal('declined');
        const decline = screen.getAllByRole('button', { name: 'DELETION_REQUEST.DECLINE' }).at(-1)!;

        fireEvent.click(decline);
        expect(screen.getByRole('alert').textContent).toBe('DELETION_REQUEST.REASON_REQUIRED');
        expect(closeRequest).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole('radio', { name: 'DELETION_REQUEST.REASON.IDENTITY_NOT_VERIFIED' }));
        fireEvent.click(decline);
        await waitFor(() => expect(closeRequest).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'form-g', responseId: 'r1', outcome: 'declined', reason: 'identity_not_verified' }));
        expect(toast).toHaveBeenCalledWith({ description: 'DELETION_REQUEST.DECLINED' });
    });

    it('explains a copy that could not be attributed and keeps the dialog open', async () => {
        closeRequest.mockResolvedValue({ error: { status: 409, data: { code: 'deletion_request_copy_unresolved' } } });
        renderModal('completed');
        fireEvent.click(screen.getAllByRole('button', { name: 'DELETION_REQUEST.MARK_DELETED' }).at(-1)!);

        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'DELETION_REQUEST.COPY_UNRESOLVED', variant: 'destructive' }));
        expect(closeModal).not.toHaveBeenCalled();
    });

    it('closes the dialog when the request was already closed', async () => {
        closeRequest.mockResolvedValue({ error: { status: 409, data: { code: 'deletion_request_closed' } } });
        renderModal('declined');
        fireEvent.click(screen.getByRole('radio', { name: 'DELETION_REQUEST.REASON.OTHER' }));
        fireEvent.click(screen.getAllByRole('button', { name: 'DELETION_REQUEST.DECLINE' }).at(-1)!);

        await waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'DELETION_REQUEST.ALREADY_CLOSED', variant: 'destructive' }));
        expect(closeModal).toHaveBeenCalled();
    });
});
