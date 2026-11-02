import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import WorkspaceTotpSection from './workspace-totp-section';

const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));

const policy: { data: any; isLoading: boolean } = { data: undefined, isLoading: false };
const mine: { data: any } = { data: { available: true, enabled: true } };
const setPolicyMock = vi.fn();
const verifyMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetWorkspaceTotpPolicyQuery: () => policy, useSetWorkspaceTotpPolicyMutation: () => [setPolicyMock, { isLoading: false }] };
});
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetMfaStatusQuery: () => mine,
        useLogoutMutation: () => [vi.fn()],
        useVerifyMfaMutation: () => [verifyMock, { isLoading: false }],
        usePostMfaChallengeMutation: () => [vi.fn(), { isLoading: false }],
        useStartTotpEnrolmentMutation: () => [vi.fn().mockResolvedValue({ data: { factorId: 'f1', secret: 'AAAA BBBB', uri: 'otpauth://totp/x?secret=AAAABBBB' } }), { reset: vi.fn() }],
        useConfirmTotpEnrolmentMutation: () => [vi.fn(), { isLoading: false, reset: vi.fn() }]
    };
});
const toastMock = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));

const OWNER = ['security.manage', 'workspace.billing'];
const ADMIN = ['security.manage'];
const renderPage = () =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceTotpSection />
        </ReduxProvider>
    );

describe('WorkspaceTotpSection (require an authenticator app for members)', () => {
    beforeEach(() => {
        access.permissions = OWNER;
        policy.data = { available: true, required: false, members: 6, membersWithoutFactor: 4 };
        policy.isLoading = false;
        mine.data = { available: true, enabled: true };
        setPolicyMock.mockReset().mockResolvedValue({ data: { available: true, required: true, members: 6, membersWithoutFactor: 4 } });
        verifyMock.mockReset().mockResolvedValue({ data: { available: true, enabled: true } });
        toastMock.mockReset();
        store.dispatch(setWorkspace({ id: 'ws-1', ownerId: 'o', workspaceName: 'acme', default: false, isPro: false }));
    });

    it('is absent while the server has the switch off', () => {
        policy.data = { available: false, required: false, members: 0, membersWithoutFactor: 0 };
        const { container } = renderPage();
        expect(container).toBeEmptyDOMElement();
    });

    it('shows the rule and who has no app yet, and passes axe', async () => {
        renderPage();
        expect(screen.getByTestId('totp-policy-state').textContent).toBe('Not required.');
        expect(screen.getByTestId('totp-policy-counts').textContent).toBe('Members without an authenticator app: 4 of 6.');
        expect(await axeViolations(document.body)).toEqual([]);
    });

    it('asks to confirm with the consequences, then turns it on', async () => {
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Require an authenticator app' }));
        const dialog = await screen.findByRole('dialog', { name: 'Require an authenticator app for all members?' });
        expect(dialog.textContent).toContain('4 of 6 members have none yet');
        expect(dialog.textContent).toContain('Nobody is signed out');
        expect(setPolicyMock).not.toHaveBeenCalled();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Require it' }));
        await waitFor(() => expect(setPolicyMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', required: true }));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith({ description: 'Members now need an authenticator app.' }));
    });

    it('turns it off at once, without asking', async () => {
        policy.data = { available: true, required: true, members: 6, membersWithoutFactor: 0 };
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Stop requiring it' }));
        await waitFor(() => expect(setPolicyMock).toHaveBeenCalledWith({ workspaceId: 'ws-1', required: false }));
    });

    it("asks for the owner's own code first when the server says enrol_first, and tries again", async () => {
        setPolicyMock.mockResolvedValueOnce({ error: { status: 409, data: { code: 'enrol_first', message: 'x' } } });
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Require an authenticator app' }));
        fireEvent.click(await screen.findByRole('button', { name: 'Require it' }));
        const gate = await screen.findByRole('dialog', { name: 'Use your own authenticator app first' });
        expect(gate.textContent).toContain('cannot lock yourself out');
        fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
        fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
        await waitFor(() => expect(verifyMock).toHaveBeenCalledWith({ code: '123456' }));
        await waitFor(() => expect(setPolicyMock).toHaveBeenCalledTimes(2));
    });

    it('offers the setup instead when the owner has no app', async () => {
        mine.data = { available: true, enabled: false };
        setPolicyMock.mockResolvedValueOnce({ error: { status: 409, data: { code: 'enrol_first' } } });
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Require an authenticator app' }));
        fireEvent.click(await screen.findByRole('button', { name: 'Require it' }));
        expect(await screen.findByText('Scan the QR code')).toBeInTheDocument();
    });

    it('lets an admin see the rule but not change it', () => {
        access.permissions = ADMIN;
        renderPage();
        expect(screen.getByText('Only owners can change this.')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Require an authenticator app' })).toBeNull();
    });

    it('says so to a member without security rights', () => {
        access.permissions = [];
        renderPage();
        expect(screen.getByText('Only owners and administrators can see this.')).toBeInTheDocument();
    });
});
