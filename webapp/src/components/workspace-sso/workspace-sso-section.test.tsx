import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ssoErrorMessage, ssoTestMessage } from '@app/lib/sso';
import type { SsoConnectionDto, SsoOverviewDto } from '@app/models/dtos/workspace-sso-dto';
import { store } from '@app/store/store';

import WorkspaceSsoSection from './workspace-sso-section';

const refetchMock = vi.fn();
const query: { data: SsoOverviewDto | undefined; isLoading: boolean; isError: boolean; refetch: typeof refetchMock } = { data: undefined, isLoading: false, isError: false, refetch: refetchMock };
const createMock = vi.fn();
const enableMock = vi.fn();
const deleteMock = vi.fn();
const settingsMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceSsoQuery: () => query,
        useCreateSsoConnectionMutation: () => [createMock, { isLoading: false }],
        useSetSsoConnectionEnabledMutation: () => [enableMock, { isLoading: false }],
        useDeleteSsoConnectionMutation: () => [deleteMock, { isLoading: false }],
        useUpdateSsoSettingsMutation: () => [settingsMock, { isLoading: false }]
    };
});

const toastMock = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));

vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme' }) };
});

let searchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({ useSearchParams: () => searchParams }));

const connection = (overrides: Partial<SsoConnectionDto> = {}): SsoConnectionDto => ({
    id: 'c1',
    type: 'saml',
    name: 'Okta',
    status: 'enabled',
    idpEntityId: 'https://idp.acme.com/entity',
    tested: true,
    testedAt: '2026-10-04T10:00:00Z',
    lastTestError: null,
    ...overrides
});

const overview = (overrides: Partial<SsoOverviewDto> = {}): SsoOverviewDto => ({
    available: true,
    serviceProvider: {
        acsUrl: 'https://sso.example.org/api/oauth/saml',
        entityId: 'https://saml.example.org',
        spMetadataUrl: 'https://sso.example.org/.well-known/sp-metadata',
        oidcRedirectUri: 'https://sso.example.org/api/oauth/oidc'
    },
    domains: ['acme.com'],
    connections: [connection()],
    settings: { ssoRequired: false, defaultRole: 'COLLABORATOR', assignableRoles: ['COLLABORATOR'], ownerBreakGlass: true },
    maxConnections: 5,
    ...overrides
});

const renderSection = () =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceSsoSection />
        </ReduxProvider>
    );

describe('WorkspaceSsoSection', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        searchParams = new URLSearchParams();
        query.data = overview();
        query.isLoading = false;
        query.isError = false;
    });

    it('shows the service provider values and the break-glass note', () => {
        renderSection();
        expect(screen.getByText('https://sso.example.org/api/oauth/saml')).toBeTruthy();
        expect(screen.getByText('https://saml.example.org')).toBeTruthy();
        expect(screen.getByText(/Break-glass:/)).toBeTruthy();
        expect(screen.getByText('Require single sign-on for acme.com')).toBeTruthy();
    });

    it('requires SSO and offers to sign out existing sessions', async () => {
        settingsMock.mockResolvedValue({ data: { ssoRequired: true, revokedSessions: 2 } });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: 'Require single sign-on' }));
        await waitFor(() => expect(settingsMock).toHaveBeenCalledWith({ workspace_id: 'ws1', body: { ssoRequired: true, revokeSessions: true } }));
        expect(toastMock).toHaveBeenCalledWith({ description: 'Single sign-on is now required. 2 sessions were signed out.' });
    });

    it('cannot require SSO without a tested, enabled connection', () => {
        query.data = overview({ connections: [connection({ tested: false, testedAt: null })] });
        renderSection();
        expect((screen.getByRole('button', { name: 'Require single sign-on' }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.getByText(/test it successfully first/)).toBeTruthy();
    });

    it('locks the enabled connection while SSO is required', () => {
        query.data = overview({ settings: { ...overview().settings, ssoRequired: true, ssoRequiredChangedAt: '2026-10-04T10:00:00Z' } });
        renderSection();
        const card = screen.getByTestId('sso-connection-c1');
        expect((within(card).getByRole('button', { name: 'Disable' }) as HTMLButtonElement).disabled).toBe(true);
        expect((within(card).getByRole('button', { name: 'Delete Okta' }) as HTMLButtonElement).disabled).toBe(true);
    });

    it('creates an OIDC connection without keeping the secret around', async () => {
        query.data = overview({ connections: [] });
        createMock.mockResolvedValue({ data: connection({ type: 'oidc' }) });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: 'Add connection' }));
        fireEvent.click(screen.getByLabelText('OpenID Connect'));
        fireEvent.change(screen.getByLabelText('Discovery URL'), { target: { value: 'https://login.acme.com/.well-known/openid-configuration' } });
        fireEvent.change(screen.getByLabelText('Client ID'), { target: { value: 'bc' } });
        fireEvent.change(screen.getByLabelText(/Client secret/), { target: { value: 's3cret' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create connection' }));
        await waitFor(() =>
            expect(createMock).toHaveBeenCalledWith({
                workspace_id: 'ws1',
                body: { type: 'oidc', name: undefined, discoveryUrl: 'https://login.acme.com/.well-known/openid-configuration', clientId: 'bc', clientSecret: 's3cret' }
            })
        );
    });

    it('explains a test result from the URL', () => {
        searchParams = new URLSearchParams('sso_test=sso_email_domain_not_allowed');
        renderSection();
        expect(screen.getByRole('status').textContent).toContain('not on one of this workspace');
    });

    it('says when SSO is off on the instance', () => {
        query.data = overview({ available: false, serviceProvider: null });
        renderSection();
        expect(screen.getByText(/not enabled on this instance/)).toBeTruthy();
    });
});

describe('sso messages', () => {
    it('only explains known codes', () => {
        expect(ssoErrorMessage('sso_seat_limit')).toContain('no free seats');
        expect(ssoErrorMessage('<script>')).toBe(ssoErrorMessage('sso_failed'));
        expect(ssoErrorMessage(null)).toBeNull();
        expect(ssoTestMessage('ok')).toContain('worked');
        expect(ssoTestMessage('whatever')).toBe(ssoTestMessage('sso_failed'));
    });
});
