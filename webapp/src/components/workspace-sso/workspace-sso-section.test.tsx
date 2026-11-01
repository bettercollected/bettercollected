import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ssoErrorMessage, ssoTestMessage } from '@app/lib/sso';
import type { SsoConnectionDto, SsoOverviewDto } from '@app/models/dtos/workspace-sso-dto';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import en from '../../../public/locales/en/common.json';
import nl from '../../../public/locales/nl/common.json';
import { SSO_SETUP_GUIDE_URL } from './sso-self-hosting-guide';
import WorkspaceSsoSection from './workspace-sso-section';

const refetchMock = vi.fn();
const query: { data: SsoOverviewDto | undefined; isLoading: boolean; isError: boolean; refetch: typeof refetchMock } = { data: undefined, isLoading: false, isError: false, refetch: refetchMock };
const createMock = vi.fn();
const enableMock = vi.fn();
const deleteMock = vi.fn();
const settingsMock = vi.fn();
const revokeKeyMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceSsoQuery: () => query,
        useCreateSsoConnectionMutation: () => [createMock, { isLoading: false }],
        useSetSsoConnectionEnabledMutation: () => [enableMock, { isLoading: false }],
        useDeleteSsoConnectionMutation: () => [deleteMock, { isLoading: false }],
        useUpdateSsoSettingsMutation: () => [settingsMock, { isLoading: false }],
        useRevokeAPIKeyMutation: () => [revokeKeyMock, { isLoading: false }]
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
    settings: { ssoRequired: false, defaultRole: 'VIEWER', assignableRoles: ['EDITOR', 'REVIEWER', 'VIEWER'], ownerBreakGlass: true },
    maxConnections: 5,
    canManage: true,
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
        // the copy fields, and again in the Entra ID help
        expect(screen.getAllByText('https://sso.example.org/api/oauth/saml')).toHaveLength(2);
        expect(screen.getAllByText('https://saml.example.org')).toHaveLength(2);
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

    describe('before locking the owner out', () => {
        const lockedOut = () => overview({ settings: { ...overview().settings, callerWouldBeLockedOut: true } });

        it('warns and asks before requiring SSO from a session it would refuse', async () => {
            query.data = lockedOut();
            settingsMock.mockResolvedValue({ data: { ssoRequired: true } });
            renderSection();
            fireEvent.click(screen.getByRole('button', { name: 'Require single sign-on' }));
            // nothing saved yet
            expect(settingsMock).not.toHaveBeenCalled();
            const warning = screen.getByTestId('sso-lockout-warning');
            expect(within(warning).getByText('Your own session would be signed out')).toBeTruthy();
            expect(warning.textContent).toContain('acme.com');
            fireEvent.click(within(warning).getByRole('button', { name: 'Require anyway' }));
            await waitFor(() => expect(settingsMock).toHaveBeenCalledWith({ workspace_id: 'ws1', body: { ssoRequired: true, revokeSessions: true, confirmLockout: true } }));
        });

        it('can be cancelled without saving', () => {
            query.data = lockedOut();
            renderSection();
            fireEvent.click(screen.getByRole('button', { name: 'Require single sign-on' }));
            fireEvent.click(within(screen.getByTestId('sso-lockout-warning')).getByRole('button', { name: 'Cancel' }));
            expect(screen.queryByTestId('sso-lockout-warning')).toBeNull();
            expect(settingsMock).not.toHaveBeenCalled();
        });

        it('shows the warning when only the server knows the session would be refused', async () => {
            settingsMock.mockResolvedValueOnce({ error: { data: { code: 'sso_lockout_unconfirmed', message: 'x' } } });
            renderSection();
            fireEvent.click(screen.getByRole('button', { name: 'Require single sign-on' }));
            await waitFor(() => expect(screen.getByTestId('sso-lockout-warning')).toBeTruthy());
            // not reported as a failure
            expect(toastMock).not.toHaveBeenCalled();
        });

        it('does not ask when the session is fine', async () => {
            settingsMock.mockResolvedValue({ data: { ssoRequired: true } });
            renderSection();
            fireEvent.click(screen.getByRole('button', { name: 'Require single sign-on' }));
            await waitFor(() => expect(settingsMock).toHaveBeenCalledTimes(1));
            expect(screen.queryByTestId('sso-lockout-warning')).toBeNull();
        });
    });

    describe('API keys that predate the requirement', () => {
        const key = (overrides = {}) => ({ id: 'k1', name: 'Zapier', prefix: 'bc_1a2b3c4d', scopes: ['forms:read', 'responses:read'], createdBy: 'u1', createdByLabel: 'Sam Owner', createdAt: '2026-09-01T10:00:00Z', lastUsedAt: null, ...overrides });
        const required = (keys: any[]) => overview({ settings: { ...overview().settings, ssoRequired: true, ssoRequiredChangedAt: '2026-10-04T10:00:00Z', apiKeys: keys } });

        it('lists them with creator and last use, and revokes one', async () => {
            query.data = required([key(), key({ id: 'k2', name: 'Reports', createdByLabel: null, lastUsedAt: '2026-10-03T09:00:00Z' })]);
            revokeKeyMock.mockResolvedValue({ data: [] });
            renderSection();
            const box = screen.getByTestId('sso-api-keys');
            expect(within(box).getByText(/2 API keys were created before single sign-on was required/)).toBeTruthy();
            expect(box.textContent).toContain('Zapier');
            expect(box.textContent).toContain('Created by Sam Owner');
            expect(box.textContent).toContain('Never used');
            // no label: the creator id; used key: its last use
            expect(box.textContent).toContain('Created by u1');
            expect(box.textContent).toContain('Last used');
            fireEvent.click(within(box).getByRole('button', { name: 'Revoke key Zapier' }));
            await waitFor(() => expect(revokeKeyMock).toHaveBeenCalledWith({ workspace_id: 'ws1', key_id: 'k1' }));
            expect(toastMock).toHaveBeenCalledWith({ description: 'Key revoked.' });
        });

        it('uses the singular for one key', () => {
            query.data = required([key()]);
            renderSection();
            expect(within(screen.getByTestId('sso-api-keys')).getByText(/1 API key was created/)).toBeTruthy();
        });

        it('shows nothing without keys, or without the requirement', () => {
            query.data = required([]);
            renderSection();
            expect(screen.queryByTestId('sso-api-keys')).toBeNull();
        });

        it('shows nothing while SSO is not required', () => {
            query.data = overview({ settings: { ...overview().settings, apiKeys: [key()] } });
            renderSection();
            expect(screen.queryByTestId('sso-api-keys')).toBeNull();
        });

        it('lets an admin who cannot manage see the keys but not revoke them here', () => {
            query.data = { ...required([key()]), canManage: false };
            renderSection();
            expect(screen.getByTestId('sso-api-keys')).toBeTruthy();
            expect(screen.queryByRole('button', { name: 'Revoke key Zapier' })).toBeNull();
        });
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

    it('shows an admin the settings read-only, with testing', () => {
        query.data = overview({ canManage: false, connections: [connection({ status: 'disabled' })] });
        renderSection();
        expect(screen.getByText(/Only a workspace owner can change single sign-on/)).toBeTruthy();
        expect(screen.queryByRole('button', { name: 'Enable' })).toBeNull();
        expect(screen.queryByRole('button', { name: 'Add connection' })).toBeNull();
        expect(screen.queryByRole('button', { name: 'Require single sign-on' })).toBeNull();
        expect(screen.getByRole('button', { name: 'Test connection' })).toBeTruthy();
    });

    it('cannot enable an untested connection', () => {
        query.data = overview({ connections: [connection({ status: 'disabled', tested: false, testedAt: null })] });
        renderSection();
        expect((screen.getByRole('button', { name: 'Enable' }) as HTMLButtonElement).disabled).toBe(true);
    });

    it('asks for a verified domain before a connection can be added', () => {
        query.data = overview({ domains: [], connections: [] });
        renderSection();
        expect(screen.queryByRole('button', { name: 'Add connection' })).toBeNull();
        expect(screen.getByText(/A connection needs a verified email domain/)).toBeTruthy();
        const links = screen.getAllByRole('link', { name: /Verify your organisation/ });
        expect(links.every((l) => l.getAttribute('href') === '/acme/dashboard/sso/domains')).toBe(true);
    });

    it('links to Domains when the server refuses a connection without one', async () => {
        query.data = overview({ connections: [] });
        createMock.mockResolvedValue({ error: { data: { code: 'sso_domain_required', message: 'Verify your domain first.' } } });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: 'Add connection' }));
        fireEvent.click(screen.getByLabelText('Paste metadata XML'));
        fireEvent.change(screen.getByLabelText('Metadata XML'), { target: { value: '<EntityDescriptor/>' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create connection' }));
        await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Verify your domain first.'));
        expect(within(screen.getByRole('alert')).getByRole('link').getAttribute('href')).toBe('/acme/dashboard/sso/domains');
    });

    it('explains a test result from the URL', () => {
        searchParams = new URLSearchParams('sso_test=sso_email_domain_not_allowed');
        renderSection();
        expect(screen.getByRole('status').textContent).toContain('not on one of this workspace');
    });

    it('shows which domain the identity provider sent for a failed test', () => {
        query.data = overview({
            connections: [connection({ tested: false, testedAt: null, lastTestError: 'sso_email_domain_not_allowed', lastTestAt: '2026-10-05T10:00:00Z', lastTestDomain: 'other-corp.org', lastTestClaims: ['email', 'upn'] })]
        });
        renderSection();
        const card = screen.getByTestId('sso-connection-c1');
        expect(card.textContent).toContain("Your identity provider sent an address at other-corp.org. This workspace's verified domains: acme.com.");
        expect(card.textContent).toContain('Claims received: email, upn');
    });

    it('shows the claims received with a missing-email test result', () => {
        searchParams = new URLSearchParams('sso_test=sso_email_missing');
        query.data = overview({
            connections: [connection({ id: 'c2', tested: false, testedAt: null, lastTestError: 'sso_email_missing', lastTestAt: '2026-10-05T10:00:00Z', lastTestClaims: ['preferred_username', 'upn'] })]
        });
        renderSection();
        const status = screen.getByRole('status');
        expect(status.textContent).toContain('did not send an email address');
        expect(status.textContent).toContain('Claims received: preferred_username, upn');
        expect(status.textContent).not.toContain('sent an address at');
    });

    it('warns that an OIDC test may reuse the IdP session, and not for SAML', () => {
        query.data = overview({ connections: [connection(), connection({ id: 'c3', type: 'oidc', name: 'Entra' })] });
        renderSection();
        expect(within(screen.getByTestId('sso-connection-c3')).getByText(/may reuse this browser/).textContent).toContain('https://login.microsoftonline.com/logout.srf');
        expect(within(screen.getByTestId('sso-connection-c1')).queryByText(/may reuse this browser/)).toBeNull();
    });

    it('shows no diagnostics once a test passed', () => {
        query.data = overview({ connections: [connection({ lastTestError: null, lastTestDomain: null, lastTestClaims: null })] });
        renderSection();
        expect(screen.queryByText(/Claims received/)).toBeNull();
    });

    it("explains Entra ID and Keycloak setup with this instance's values", () => {
        renderSection();
        const help = screen.getByTestId('sso-entra-help');
        expect(within(help).getByText('Setting up Microsoft Entra ID')).toBeTruthy();
        expect(help.textContent).toContain('https://saml.example.org');
        expect(help.textContent).toContain('https://sso.example.org/api/oauth/saml');
        expect(within(help).getAllByText('https://sso.example.org/api/oauth/oidc')).toHaveLength(2);
        expect(help.textContent).toContain('user.mail');
        expect(help.textContent).toContain('optional claim');
        expect(help.textContent).toContain('Keycloak');
        expect(help.hasAttribute('open')).toBe(false);
    });

    it('says when SSO is off on the instance', () => {
        query.data = overview({ available: false, serviceProvider: null });
        renderSection();
        expect(screen.getByText(/not enabled on this instance/)).toBeTruthy();
    });

    it('says when SSO is off on purpose (reason disabled)', () => {
        query.data = overview({ available: false, reason: 'disabled', serviceProvider: null });
        renderSection();
        const box = screen.getByTestId('sso-unavailable');
        expect(box.getAttribute('data-reason')).toBe('disabled');
        expect(box.textContent).toContain('not enabled on this instance');
        expect(within(box).queryByTestId('sso-self-hosting')).toBeNull();
    });

    it('says SSO is switched on but not fully set up, without blaming SSO_ENABLED', () => {
        query.data = overview({ available: false, reason: 'not_configured', serviceProvider: null });
        renderSection();
        const box = screen.getByTestId('sso-unavailable');
        expect(box.getAttribute('data-reason')).toBe('not_configured');
        expect(box.textContent).toContain('switched on but not fully set up on this instance yet');
        expect(box.textContent).not.toContain('SSO_ENABLED');
        expect(box.textContent).not.toContain('not enabled');
        // names or values of settings never reach the page
        expect(box.textContent).not.toMatch(/SSO_POLIS|SSO_REDIRECT|https?:/);
        // a hosted workspace admin is pointed at the instance's administrator or support;
        // the setup guide is a secondary link for people running their own instance
        expect(box.textContent).toContain('Ask the administrator or support team of this instance to finish the setup.');
        expect(box.textContent).not.toContain('docs/sso.md');
        const guide = within(box).getByRole('link', { name: 'single sign-on setup guide' });
        expect(guide.getAttribute('href')).toBe(SSO_SETUP_GUIDE_URL);
        expect(guide.getAttribute('rel')).toBe('noopener noreferrer');
    });

    it('has the not-set-up text in English and Dutch', () => {
        for (const locale of [en, nl] as any[]) {
            expect(locale.SSO.NOT_CONFIGURED).toBeTruthy();
            expect(locale.SSO.NOT_CONFIGURED).not.toContain('SSO_ENABLED');
            expect(locale.SSO.NOT_ENABLED).toContain('SSO_ENABLED');
            expect(locale.SCIM.NOT_CONFIGURED).toBeTruthy();
            expect(locale.SCIM.NOT_CONFIGURED).not.toContain('SSO_ENABLED');
            expect(locale.SSO.NOT_CONFIGURED).not.toContain('docs/sso.md');
            expect(locale.SCIM.NOT_CONFIGURED).not.toContain('docs/sso.md');
            expect(locale.SSO.SELF_HOSTING).toMatch(/<1>.+<\/1>/);
        }
        expect(nl.SSO.NOT_CONFIGURED).toContain('nog niet helemaal ingesteld');
    });
});

describe('hardening texts', () => {
    const keys = ['LOCKOUT_TITLE', 'LOCKOUT_BODY', 'LOCKOUT_CONFIRM', 'LOCKOUT_CANCEL', 'KEYS_TITLE', 'KEYS_INTRO_one', 'KEYS_INTRO_other', 'KEY_CREATED_BY', 'KEY_CREATED_AT', 'KEY_LAST_USED', 'KEY_NEVER_USED', 'KEY_REVOKE', 'KEY_REVOKE_LABEL', 'KEY_REVOKED', 'KEY_REVOKE_FAILED'];

    it('exist in English and Dutch with the same placeholders', () => {
        for (const key of keys) {
            const english = (en as any).SSO[key];
            const dutch = (nl as any).SSO[key];
            expect(english, key).toBeTruthy();
            expect(dutch, key).toBeTruthy();
            expect(dutch.match(/{{\w+}}/g)?.sort(), key).toEqual(english.match(/{{\w+}}/g)?.sort());
        }
        expect((nl as any).SSO.KEYS_INTRO_other).toContain('blijven werken');
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

    it('tells a missing email apart from a wrong domain', () => {
        expect(ssoErrorMessage('sso_email_missing')).toContain("didn't send an email address");
        expect(ssoErrorMessage('sso_email_missing')).not.toBe(ssoErrorMessage('sso_email_domain_not_allowed'));
        const test = ssoTestMessage('sso_email_missing') ?? '';
        expect(test).toContain('user.mail');
        expect(test).toContain('user.userprincipalname');
        expect(test).toContain('optional claim');
        expect(test).toContain('Keycloak');
    });
});
