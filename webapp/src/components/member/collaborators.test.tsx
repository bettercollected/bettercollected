import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RuntimeFlagsProvider from '@app/shared/hocs/runtime-flags-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import Collaborators from './collaborators';

const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));

vi.mock('@app/store/workspaces/members-n-invitations-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetWorkspaceMembersQuery: () => ({ data: [], isLoading: false }) };
});

// MembersTable has its own tests
vi.mock('../settings/members-table', () => ({ default: () => <p>members table</p> }));

const sso: { data: any; skipped: boolean[] } = { data: undefined, skipped: [] };
const scim: { data: any } = { data: undefined };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceSsoQuery: (_id: string, options: { skip?: boolean }) => {
            sso.skipped.push(!!options?.skip);
            return { data: options?.skip ? undefined : sso.data };
        },
        useGetWorkspaceScimQuery: (_id: string, options: { skip?: boolean }) => ({ data: options?.skip ? undefined : scim.data })
    };
});

const ADMIN = ['members.manage', 'security.manage', 'workspace.manage'];
const connection = (status: 'enabled' | 'disabled') => ({ id: 'c1', type: 'saml', name: 'IdP', status, tested: true });

const renderPage = (ssoEnabled = true) =>
    render(
        <RuntimeFlagsProvider flags={{ ssoEnabled }}>
            <ReduxProvider store={store}>
                <Collaborators />
            </ReduxProvider>
        </RuntimeFlagsProvider>
    );

const NOTE_TITLE = /MEMBERS\.SSO_REMOVAL\.TITLE|Removing a member does not keep them out/;

describe('members page: removal under single sign-on', () => {
    beforeEach(() => {
        access.permissions = ADMIN;
        sso.data = { available: true, connections: [connection('enabled')], domains: ['example.com'] };
        sso.skipped = [];
        scim.data = { available: true, directory: null };
        store.dispatch(setWorkspace({ id: 'ws1', workspaceName: 'acme', title: 'Acme' } as any));
    });

    it('says to disable the account at the identity provider while a connection is on', () => {
        renderPage();
        expect(screen.getByRole('note').textContent).toMatch(NOTE_TITLE);
        expect(screen.getByRole('note').textContent).toMatch(/WITHOUT_DIRECTORY|disable their account at your identity provider/);
    });

    it('points to the directory once directory sync is connected', () => {
        scim.data = { available: true, directory: { id: 'd1', name: 'Okta' } };
        renderPage();
        expect(screen.getByRole('note').textContent).toMatch(/\.WITH_DIRECTORY|deactivate them in your directory/);
    });

    it('says nothing without an enabled connection', () => {
        sso.data = { available: true, connections: [connection('disabled')], domains: [] };
        renderPage();
        expect(screen.queryByRole('note')).toBeNull();
        expect(screen.getByText('members table')).toBeTruthy();
    });

    it('does not ask for the SSO settings when SSO is off on the instance or the member cannot see them', () => {
        renderPage(false);
        expect(screen.queryByRole('note')).toBeNull();
        expect(sso.skipped.every(Boolean)).toBe(true);

        sso.skipped = [];
        access.permissions = ['members.manage'];
        renderPage(true);
        expect(screen.queryAllByRole('note')).toHaveLength(0);
        expect(sso.skipped.every(Boolean)).toBe(true);
    });
});
