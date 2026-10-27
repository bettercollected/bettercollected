import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import enBuilder from '@app/../public/locales/en/builder.json';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import CaseSystemPage from './page';

const en = enBuilder.REGISTRATION as any;

const status = { data: { enabled: true } as { enabled: boolean } | undefined, isLoading: false };
vi.mock('@app/store/workspaces/registration-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetRegistrationStatusQuery: () => status,
        useGetRegistrationServicesQuery: () => ({ data: [], isLoading: false, isError: false, refetch: vi.fn() }),
        useCreateRegistrationServiceMutation: () => [vi.fn(), { isLoading: false, reset: vi.fn() }],
        useUpdateRegistrationServiceMutation: () => [vi.fn(), { isLoading: false, reset: vi.fn() }],
        useDeleteRegistrationServiceMutation: () => [vi.fn(), { isLoading: false }],
        useTestRegistrationServiceMutation: () => [vi.fn(), { isLoading: false }]
    };
});
let permissions = new Set<string>();
let ready = true;
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (p: string) => permissions.has(p), ready, isLoading: !ready }) }));
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme', title: 'Acme' }) };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

beforeEach(() => {
    status.data = { enabled: true };
    status.isLoading = false;
    permissions = new Set([WorkspacePermission.WORKSPACE_MANAGE]);
    ready = true;
});

describe('Case system page', () => {
    it('shows the services to an admin while the feature is on', () => {
        render(<CaseSystemPage />, { wrapper });
        expect(screen.getByRole('button', { name: en.SERVICES.ADD })).toBeInTheDocument();
    });

    it('shows nothing to manage when the status says the feature is off', () => {
        status.data = { enabled: false };
        render(<CaseSystemPage />, { wrapper });
        expect(screen.getByText(en.SERVICES.TURNED_OFF)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: en.SERVICES.ADD })).toBeNull();
    });

    it('shows nothing to manage while the status or the permissions are unknown', () => {
        status.data = undefined;
        status.isLoading = true;
        render(<CaseSystemPage />, { wrapper });
        expect(screen.queryByRole('button', { name: en.SERVICES.ADD })).toBeNull();
    });

    it('tells members who are not admins that it is for admins', () => {
        permissions = new Set([WorkspacePermission.FORM_EDIT]);
        render(<CaseSystemPage />, { wrapper });
        expect(screen.getByText(en.SERVICES.ONLY_ADMINS)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: en.SERVICES.ADD })).toBeNull();
    });
});
