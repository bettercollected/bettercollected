import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TransferOwnershipDialog, { transferBlocker } from '@app/components/member/transfer-ownership-dialog';
import InviteMemberModal from '@app/components/modal-views/modals/invite-member-modal';
import { memberRole, toWorkspaceRole } from '@app/models/enums/workspace-role';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import MembersTable from './members-table';

const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));

const updateRoleMock = vi.fn();
const transferMock = vi.fn();
const inviteMock = vi.fn();
vi.mock('@app/store/workspaces/members-n-invitations-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useUpdateWorkspaceMemberRoleMutation: () => [updateRoleMock, { isLoading: false }],
        useTransferWorkspaceOwnershipMutation: () => [transferMock, { isLoading: false }],
        useInviteToWorkspaceMutation: () => [inviteMock, { isLoading: false }],
        useGetWorkspaceMembersQuery: () => ({ data: [] }),
        useResendWorkspaceInvitationMutation: () => [vi.fn(), { isLoading: false }]
    };
});

const OWNER_PERMISSIONS = ['workspace.billing', 'workspace.manage', 'members.manage', 'form.read'];
const ADMIN_PERMISSIONS = ['workspace.manage', 'members.manage', 'form.read'];
const VIEWER_PERMISSIONS = ['form.read', 'response.read', 'analytics.read'];

const member = (id: string, role: string | null, roles: string[] = role ? [role] : []) => ({ id, email: `${id}@example.com`, firstName: id, lastName: '', roles, role, joined: '2026-10-01T00:00:00Z' });
const MEMBERS = [member('owner', 'OWNER', ['ADMIN']), member('me', 'ADMIN'), member('editor', 'EDITOR')];

// react-data-table-component reads the colour scheme
if (!window.matchMedia) {
    window.matchMedia = ((query: string) => ({ matches: false, media: query, onchange: null, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false })) as any;
}

const renderWith = (ui: React.ReactElement) => render(<ReduxProvider store={store}>{ui}</ReduxProvider>);

describe('workspace roles', () => {
    it('reads COLLABORATOR as EDITOR and ignores unknown roles', () => {
        expect(toWorkspaceRole('COLLABORATOR')).toBe('EDITOR');
        expect(toWorkspaceRole('privacy_officer')).toBe('PRIVACY_OFFICER');
        expect(toWorkspaceRole('FORM_CREATOR')).toBeUndefined();
        expect(memberRole({ role: null, roles: ['COLLABORATOR'] })).toBe('EDITOR');
    });

    it('says why ownership cannot move', () => {
        expect(transferBlocker({ default: true }, 'ADMIN')).toBe('MEMBER_ROLES.TRANSFER_PERSONAL');
        expect(transferBlocker({ default: false, isPro: true }, 'ADMIN')).toBe('MEMBER_ROLES.TRANSFER_PAID');
        expect(transferBlocker({ default: false, isPro: false }, 'EDITOR')).toBe('MEMBER_ROLES.TRANSFER_ONLY_ADMINS');
        expect(transferBlocker({ default: false, isPro: false }, 'ADMIN')).toBeUndefined();
    });
});

describe('MembersTable', () => {
    beforeEach(() => {
        updateRoleMock.mockReset();
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'owner', workspaceName: 'acme', default: false, isPro: false }));
        store.dispatch(setAuth({ id: 'me', email: 'me@example.com' }));
    });

    it('gives those who manage members a role picker, except for the owner and themselves', () => {
        access.permissions = ADMIN_PERMISSIONS;
        renderWith(<MembersTable data={MEMBERS} />);

        expect(screen.getAllByRole('combobox', { name: 'MEMBERS.ROLE' })).toHaveLength(1);
        expect(screen.getByTestId('member-role-owner').textContent).toBe('WORKSPACE_ROLES.OWNER.NAME');
        expect(screen.getByTestId('member-role-me').textContent).toBe('WORKSPACE_ROLES.ADMIN.NAME');
        // each role's one-line description is on hand
        expect(screen.getByTestId('member-role-owner').getAttribute('title')).toBe('WORKSPACE_ROLES.OWNER.DESCRIPTION');
    });

    it('shows roles read-only, without member actions, to everyone else', () => {
        access.permissions = VIEWER_PERMISSIONS;
        renderWith(<MembersTable data={MEMBERS} />);

        expect(screen.queryByRole('combobox')).toBeNull();
        expect(screen.getByTestId('member-role-editor').textContent).toBe('WORKSPACE_ROLES.EDITOR.NAME');
        expect(screen.queryByText('Open menu')).toBeNull();
    });

    it('lists a deleted account by id only, without a role picker', () => {
        access.permissions = ADMIN_PERMISSIONS;
        renderWith(<MembersTable data={[{ ...member('gone', 'EDITOR'), email: null, firstName: null, accountDeleted: true }]} />);

        expect(screen.getByTestId('member-deleted-gone').textContent).toBe('MEMBER_ROLES.DELETED_ACCOUNT');
        expect(screen.queryByRole('combobox')).toBeNull();
        expect(screen.getByTestId('member-role-gone').textContent).toBe('WORKSPACE_ROLES.EDITOR.NAME');
    });

    it('shows an unknown role as unknown', () => {
        access.permissions = VIEWER_PERMISSIONS;
        renderWith(<MembersTable data={[member('future', null, ['SOMETHING_NEW'])]} />);

        expect(screen.getByTestId('member-role-future').textContent).toBe('WORKSPACE_ROLES.UNKNOWN');
    });
});

describe('TransferOwnershipDialog', () => {
    beforeEach(() => {
        transferMock.mockReset();
        access.permissions = OWNER_PERMISSIONS;
        store.dispatch(setAuth({ id: 'owner', email: 'owner@example.com' }));
    });

    it('asks for confirmation, then hands the workspace over', async () => {
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'owner', workspaceName: 'acme', default: false, isPro: false }));
        transferMock.mockResolvedValue({ data: { message: 'Ownership transferred.', ownerId: 'admin' } });
        renderWith(<TransferOwnershipDialog open onOpenChange={() => {}} member={member('admin', 'ADMIN') as any} />);

        expect(screen.getByText('MEMBER_ROLES.TRANSFER_DESCRIPTION')).toBeDefined();
        fireEvent.click(screen.getByRole('button', { name: 'MEMBER_ROLES.TRANSFER_OWNERSHIP' }));

        await waitFor(() => expect(transferMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', userId: 'admin' }));
        await waitFor(() => expect(store.getState().workspace.ownerId).toBe('admin'));
    });

    it('explains and refuses a workspace on a paid plan', () => {
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'owner', workspaceName: 'acme', default: false, isPro: true }));
        renderWith(<TransferOwnershipDialog open onOpenChange={() => {}} member={member('admin', 'ADMIN') as any} />);

        expect(screen.getByText('MEMBER_ROLES.TRANSFER_PAID')).toBeDefined();
        const confirm = screen.getByRole('button', { name: 'MEMBER_ROLES.TRANSFER_OWNERSHIP' }) as HTMLButtonElement;
        expect(confirm.disabled).toBe(true);
        fireEvent.click(confirm);
        expect(transferMock).not.toHaveBeenCalled();
    });
});

describe('InviteMemberModal', () => {
    beforeEach(() => {
        inviteMock.mockReset();
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'owner', workspaceName: 'acme' }));
    });

    it('invites as an Editor unless another role is chosen', async () => {
        inviteMock.mockResolvedValue({ data: {} });
        renderWith(<InviteMemberModal />);

        expect(screen.getByRole('combobox', { name: 'MEMBERS.ROLE' })).toBeDefined();
        expect(screen.getByText('WORKSPACE_ROLES.EDITOR.DESCRIPTION')).toBeDefined();
        fireEvent.change(screen.getByPlaceholderText('ENTER_EMAIL'), { target: { value: 'new@example.com' } });
        fireEvent.submit(screen.getByRole('button', { name: 'BUTTON.SEND_INVITATION' }).closest('form') as HTMLFormElement);

        await waitFor(() => expect(inviteMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', body: { role: 'EDITOR', email: 'new@example.com' } }));
    });
});
