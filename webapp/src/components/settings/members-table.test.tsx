import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MakeBillingOwnerDialog, { billingOwnerBlocker } from '@app/components/member/make-billing-owner-dialog';
import InviteMemberModal, { INVITE_FIELD_CLASS } from '@app/components/modal-views/modals/invite-member-modal';
import { assignableRoles, isBillingOwnerOf, memberRole, toWorkspaceRole } from '@app/models/enums/workspace-role';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import MembersTable from './members-table';

const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));

const updateRoleMock = vi.fn();
const billingMock = vi.fn();
const inviteMock = vi.fn();
vi.mock('@app/store/workspaces/members-n-invitations-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useUpdateWorkspaceMemberRoleMutation: () => [updateRoleMock, { isLoading: false }],
        useMakeBillingOwnerMutation: () => [billingMock, { isLoading: false }],
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

    it('says why the billing owner cannot change', () => {
        expect(billingOwnerBlocker({ default: true }, 'OWNER')).toBe('MEMBER_ROLES.BILLING_PERSONAL');
        expect(billingOwnerBlocker({ default: false, isPro: true }, 'OWNER')).toBe('MEMBER_ROLES.BILLING_PAID');
        expect(billingOwnerBlocker({ default: false, isPro: false }, 'ADMIN')).toBe('MEMBER_ROLES.BILLING_ONLY_OWNERS');
        expect(billingOwnerBlocker({ default: false, isPro: false }, 'OWNER')).toBeUndefined();
    });

    it('offers Owner only to owners', () => {
        expect(assignableRoles(false)).not.toContain('OWNER');
        expect(assignableRoles(true)[0]).toBe('OWNER');
    });

    it('knows the billing owner from the workspace, else from the list', () => {
        expect(isBillingOwnerOf({ id: 'a' }, { ownerId: 'a' })).toBe(true);
        expect(isBillingOwnerOf({ id: 'b', billingOwner: true }, { ownerId: 'a' })).toBe(false);
        expect(isBillingOwnerOf({ id: 'b', billingOwner: true }, null)).toBe(true);
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

    it('marks the billing owner and keeps other owners from Admins', () => {
        access.permissions = ADMIN_PERMISSIONS;
        renderWith(<MembersTable data={[...MEMBERS, member('co', 'OWNER')]} />);

        expect(screen.getByTestId('billing-owner-owner')).toBeDefined();
        expect(screen.queryByTestId('billing-owner-co')).toBeNull();
        // an Admin changes neither owner: only the editor gets a picker
        expect(screen.getAllByRole('combobox', { name: 'MEMBERS.ROLE' })).toHaveLength(1);
        expect(screen.getByTestId('member-role-co').textContent).toBe('WORKSPACE_ROLES.OWNER.NAME');
        // and has no actions on them: menus for themselves and the editor only
        expect(screen.getAllByText('Open menu')).toHaveLength(2);
    });

    it('lets an owner change another owner, never the billing owner', () => {
        access.permissions = OWNER_PERMISSIONS;
        store.dispatch(setAuth({ id: 'co', email: 'co@example.com' }));
        renderWith(<MembersTable data={[...MEMBERS, member('co', 'OWNER'), member('co2', 'OWNER')]} />);

        // the Admin, the editor and the other co-owner; not the billing owner
        // and not oneself
        expect(screen.getAllByRole('combobox', { name: 'MEMBERS.ROLE' })).toHaveLength(3);
        expect(screen.getByTestId('member-role-owner').textContent).toBe('WORKSPACE_ROLES.OWNER.NAME');
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

describe('MakeBillingOwnerDialog', () => {
    beforeEach(() => {
        billingMock.mockReset();
        access.permissions = OWNER_PERMISSIONS;
        store.dispatch(setAuth({ id: 'owner', email: 'owner@example.com' }));
    });

    it('asks for confirmation, then makes another owner the billing owner', async () => {
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'owner', workspaceName: 'acme', default: false, isPro: false }));
        billingMock.mockResolvedValue({ data: { message: 'Billing owner changed.', ownerId: 'co' } });
        renderWith(<MakeBillingOwnerDialog open onOpenChange={() => {}} member={member('co', 'OWNER') as any} />);

        expect(screen.getByText('MEMBER_ROLES.BILLING_DESCRIPTION')).toBeDefined();
        fireEvent.click(screen.getByRole('button', { name: 'MEMBER_ROLES.MAKE_BILLING_OWNER' }));

        await waitFor(() => expect(billingMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', userId: 'co' }));
        await waitFor(() => expect(store.getState().workspace.ownerId).toBe('co'));
    });

    it('explains and refuses a workspace on a paid plan', () => {
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'owner', workspaceName: 'acme', default: false, isPro: true }));
        renderWith(<MakeBillingOwnerDialog open onOpenChange={() => {}} member={member('co', 'OWNER') as any} />);

        expect(screen.getByText('MEMBER_ROLES.BILLING_PAID')).toBeDefined();
        const confirm = screen.getByRole('button', { name: 'MEMBER_ROLES.MAKE_BILLING_OWNER' }) as HTMLButtonElement;
        expect(confirm.disabled).toBe(true);
        fireEvent.click(confirm);
        expect(billingMock).not.toHaveBeenCalled();
    });

    it('refuses a member who is not an owner', () => {
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'owner', workspaceName: 'acme', default: false, isPro: false }));
        renderWith(<MakeBillingOwnerDialog open onOpenChange={() => {}} member={member('admin', 'ADMIN') as any} />);

        expect(screen.getByText('MEMBER_ROLES.BILLING_ONLY_OWNERS')).toBeDefined();
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

    it('labels the email field and lines it up with the role field', () => {
        renderWith(<InviteMemberModal />);

        const email = screen.getByLabelText('ENTER_EMAIL');
        const role = screen.getByRole('combobox', { name: 'MEMBERS.ROLE' });
        expect(email.getAttribute('type')).toBe('email');
        for (const token of INVITE_FIELD_CLASS.split(' ')) {
            expect(email.className.split(' ')).toContain(token);
            expect(role.className.split(' ')).toContain(token);
        }
        expect(INVITE_FIELD_CLASS.split(' ')).toContain('w-full');
        expect(screen.getByRole('button', { name: 'BUTTON.CLOSE' })).toBeDefined();
    });
});
