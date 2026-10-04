import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ssoErrorMessage } from '@app/lib/sso';
import type { ScimOverviewDto } from '@app/models/dtos/workspace-scim-dto';
import { store } from '@app/store/store';

import WorkspaceScimSection from './workspace-scim-section';

const refetchMock = vi.fn();
const query: { data: ScimOverviewDto | undefined; isLoading: boolean; isError: boolean; refetch: typeof refetchMock } = { data: undefined, isLoading: false, isError: false, refetch: refetchMock };
const createMock = vi.fn();
const rotateMock = vi.fn();
const deleteMock = vi.fn();
const roleMock = vi.fn();
const resyncMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceScimQuery: () => query,
        useCreateScimDirectoryMutation: () => [createMock, { isLoading: false }],
        useRotateScimTokenMutation: () => [rotateMock, { isLoading: false }],
        useDeleteScimDirectoryMutation: () => [deleteMock, { isLoading: false }],
        useSetScimGroupRoleMutation: () => [roleMock, { isLoading: false }],
        useResyncScimDirectoryMutation: () => [resyncMock, { isLoading: false }]
    };
});

const toastMock = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));

vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme' }) };
});

vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }));

const directory = {
    id: 'd1',
    type: 'okta-scim-v2',
    typeLabel: 'Okta',
    name: 'Okta',
    scimEndpoint: 'https://sso.example.org/api/scim/v2.0/dir-1',
    lastEventAt: '2026-10-04T10:00:00Z',
    lastEventType: 'user.created'
};

const overview = (overrides: Partial<ScimOverviewDto> = {}): ScimOverviewDto => ({
    available: true,
    hasVerifiedDomain: true,
    directory,
    types: [
        { type: 'generic-scim-v2', label: 'Generic SCIM v2.0' },
        { type: 'okta-scim-v2', label: 'Okta' }
    ],
    counts: { provisioned: 3, deprovisioned: 1, failed: 1, ignored: 0, users: 5 },
    issues: [{ email: 'max@full.org', state: 'failed', reason: 'seat_limit', message: 'The workspace has no free seat.', at: null }],
    groups: [{ id: 'g1', name: 'Admins', role: 'ADMIN', members: 2 }],
    defaultRole: 'COLLABORATOR',
    mappableRoles: ['ADMIN', 'COLLABORATOR'],
    canManage: true,
    ...overrides
});

const renderSection = () =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceScimSection />
        </ReduxProvider>
    );

describe('WorkspaceScimSection', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        query.isLoading = false;
        query.isError = false;
    });

    it('creates a directory and shows the URL and token once', async () => {
        query.data = overview({ directory: null, counts: {}, issues: [], groups: [] });
        createMock.mockResolvedValue({ data: { directory, scimEndpoint: directory.scimEndpoint, bearerToken: 'tok-123' } });
        renderSection();

        fireEvent.change(screen.getByLabelText('Identity provider'), { target: { value: 'okta-scim-v2' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create directory' }));

        await waitFor(() => expect(screen.getByTestId('scim-credentials')).toBeTruthy());
        expect(createMock).toHaveBeenCalledWith({ workspace_id: 'ws1', body: { type: 'okta-scim-v2' } });
        expect(screen.getByText('tok-123')).toBeTruthy();
        fireEvent.click(screen.getByRole('button', { name: /copied them/ }));
        expect(screen.queryByText('tok-123')).toBeNull();
    });

    it('needs a verified domain to create a directory', () => {
        query.data = overview({ directory: null, hasVerifiedDomain: false });
        renderSection();
        expect((screen.getByRole('button', { name: 'Create directory' }) as HTMLButtonElement).disabled).toBe(true);
    });

    it('shows status, failures and the group mapping', () => {
        query.data = overview();
        renderSection();
        expect(screen.getByText('Okta')).toBeTruthy();
        expect(screen.getByTestId('scim-issues').textContent).toContain('max@full.org');
        expect(screen.getByTestId('scim-issues').textContent).toContain('no free seat');
        expect((screen.getByLabelText('Role for Admins') as HTMLSelectElement).value).toBe('ADMIN');
    });

    it('maps a group to a role', async () => {
        query.data = overview();
        roleMock.mockResolvedValue({ data: {} });
        renderSection();
        fireEvent.change(screen.getByLabelText('Role for Admins'), { target: { value: '' } });
        await waitFor(() => expect(roleMock).toHaveBeenCalledWith({ workspace_id: 'ws1', group_id: 'g1', role: null }));
    });

    it('confirms before deleting and explains members stay', async () => {
        query.data = overview();
        const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
        expect(confirm.mock.calls[0][0]).toContain('Members stay');
        expect(deleteMock).not.toHaveBeenCalled();
        confirm.mockReturnValue(true);
        deleteMock.mockResolvedValue({ data: null });
        fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
        await waitFor(() => expect(deleteMock).toHaveBeenCalledWith({ workspace_id: 'ws1' }));
        confirm.mockRestore();
    });

    it('is read-only for admins', () => {
        query.data = overview({ canManage: false });
        renderSection();
        expect(screen.queryByRole('button', { name: 'Rotate token' })).toBeNull();
        expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
        expect((screen.getByLabelText('Role for Admins') as HTMLSelectElement).disabled).toBe(true);
    });

    it('explains a deprovisioned SSO sign-in', () => {
        expect(ssoErrorMessage('sso_deprovisioned')).toContain('directory');
    });
});
