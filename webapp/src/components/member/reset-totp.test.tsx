import React from 'react';

import MemberOptions from '@Components/datatable/member-options';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import MembersTable from '../settings/members-table';
import ResetTotpDialog, { resetFailureKey } from './reset-totp-dialog';

const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));

const resetMock = vi.fn();
const verifyMock = vi.fn();
const mine: { data: any } = { data: { available: true, enabled: true } };
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetMfaStatusQuery: () => mine,
        useLogoutMutation: () => [vi.fn()],
        useVerifyMfaMutation: () => [verifyMock, { isLoading: false }],
        usePostMfaChallengeMutation: () => [vi.fn(), { isLoading: false }]
    };
});
vi.mock('@app/store/workspaces/members-n-invitations-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useResetMemberTotpMutation: () => [resetMock, { isLoading: false }],
        useResendWorkspaceInvitationMutation: () => [vi.fn(), { isLoading: false }],
        useUpdateWorkspaceMemberRoleMutation: () => [vi.fn(), { isLoading: false }]
    };
});
const toastMock = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));

if (!window.matchMedia) {
    window.matchMedia = ((query: string) => ({ matches: false, media: query, onchange: null, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false })) as any;
}

const OWNER = ['workspace.billing', 'workspace.manage', 'members.manage'];
const ADMIN = ['workspace.manage', 'members.manage'];
const member = (id: string, totpEnabled: boolean | null | undefined, role = 'EDITOR') => ({ id, email: `${id}@example.org`, firstName: id, lastName: 'Voorbeeld', roles: [role], role, joined: '2026-10-01T00:00:00Z', totpEnabled });
const renderWith = (ui: React.ReactElement) => render(<ReduxProvider store={store}>{ui}</ReduxProvider>);
const openMenu = () => fireEvent.pointerDown(screen.getByRole('button', { name: /More actions/ }), { button: 0, ctrlKey: false });

describe('the member list and the second factor', () => {
    beforeEach(() => {
        resetMock.mockReset().mockResolvedValue({ data: undefined });
        verifyMock.mockReset().mockResolvedValue({ data: { available: true, enabled: true } });
        toastMock.mockReset();
        access.permissions = OWNER;
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'someone-else', workspaceName: 'acme', default: false, isPro: false }));
        store.dispatch(setAuth({ id: 'me', email: 'me@example.org' }));
    });

    it('shows who has an authenticator app while the server has the switch on', () => {
        renderWith(<MembersTable data={[member('ada', true), member('bram', false)]} />);
        expect(screen.getByText('Authenticator app')).toBeInTheDocument();
        expect(screen.getByText('Set up')).toBeInTheDocument();
        expect(screen.getByText('Not set up')).toBeInTheDocument();
    });

    it('has no column while the switch is off (the field is null)', () => {
        renderWith(<MembersTable data={[member('ada', null), member('bram', undefined)]} />);
        expect(screen.queryByText('Authenticator app')).toBeNull();
    });

    it('offers an owner "Reset second factor" for another member who has an app', async () => {
        renderWith(<MemberOptions member={member('ada', true) as any} workspaceId="ws-1" />);
        openMenu();
        fireEvent.click(await screen.findByText('Reset second factor'));
        expect(await screen.findByRole('dialog', { name: 'Reset the second factor of this member?' })).toBeInTheDocument();
        expect(screen.getByText(/Their sessions end and they are emailed/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
        await waitFor(() => expect(resetMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', userId: 'ada' }));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith({ description: 'The second factor was reset.' }));
    });

    it.each([
        ['an admin who is not an owner', ADMIN, member('ada', true)],
        ['a member without an app', OWNER, member('ada', false)],
        ["the owner's own row", OWNER, member('me', true)],
        ['a member while the switch is off', OWNER, member('ada', null)]
    ])('does not offer it for %s', async (_name, permissions, who) => {
        access.permissions = permissions;
        renderWith(<MemberOptions member={who as any} workspaceId="ws-1" />);
        if (screen.queryByRole('button', { name: /More actions/ })) {
            openMenu();
            await screen.findByRole('menuitem');
        }
        expect(screen.queryByText('Reset second factor')).toBeNull();
    });

    it('says why the server refused, in words and without a stack trace', async () => {
        resetMock.mockResolvedValue({ error: { status: 409, data: { code: 'reset_not_allowed', message: 'x' } } });
        renderWith(<ResetTotpDialog workspaceId="ws-1" member={member('ada', true) as any} onClose={vi.fn()} />);
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
        await waitFor(() => expect(toastMock).toHaveBeenCalled());
        expect(toastMock.mock.calls[0][0].description).toMatch(/also reaches another workspace/);
        expect(resetFailureKey({ status: 409, code: 'reset_self' })).toBe('STAFF.MFA.RESET.SELF');
        expect(resetFailureKey({ status: 409, code: 'reset_admin_not_allowed' })).toBe('STAFF.MFA.RESET.ADMIN_NOT_ALLOWED');
        expect(resetFailureKey({ status: 404 })).toBe('STAFF.MFA.RESET.GONE');
        expect(resetFailureKey({ status: 500 })).toBe('STAFF.MFA.RESET.FAILED');
    });

    it('names the administrator case in words', async () => {
        resetMock.mockResolvedValue({ error: { status: 409, data: { code: 'reset_admin_not_allowed', message: 'x' } } });
        renderWith(<ResetTotpDialog workspaceId="ws-1" member={member('ada', true) as any} onClose={vi.fn()} />);
        fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
        await waitFor(() => expect(toastMock).toHaveBeenCalled());
        expect(toastMock.mock.calls[0][0].description).toMatch(/administrator of this service/);
    });

    it("asks for the owner's own code on enrol_first, then tries the reset again", async () => {
        resetMock.mockResolvedValueOnce({ error: { status: 409, data: { code: 'enrol_first', message: 'x' } } }).mockResolvedValueOnce({ data: undefined });
        renderWith(<ResetTotpDialog workspaceId="ws-1" member={member('ada', true) as any} onClose={vi.fn()} />);
        fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
        expect(await screen.findByRole('dialog', { name: 'Use your own authenticator app first' })).toBeInTheDocument();
        expect(toastMock).not.toHaveBeenCalled();
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
        await waitFor(() => expect(verifyMock).toHaveBeenCalledWith({ code: '123456' }));
        await waitFor(() => expect(resetMock).toHaveBeenCalledTimes(2));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith({ description: 'The second factor was reset.' }));
    });
});
