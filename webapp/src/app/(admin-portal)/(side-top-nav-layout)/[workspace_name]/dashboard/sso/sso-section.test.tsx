// The Single sign-on section with the SSO flag on and off.
import React from 'react';

import { redirect } from 'next/navigation';

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission as P } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import RuntimeFlagsProvider from '@app/shared/hocs/runtime-flags-provider';

import SSOSectionLayout from './_components/sso-section-layout';
import SsoPage from './page';

let pathname = '/acme/dashboard/sso';
vi.mock('next/navigation', () => ({ usePathname: () => pathname, redirect: vi.fn() }));

let granted: Array<string> = [P.SECURITY_MANAGE];
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => granted.includes(permission), ready: true, isLoading: false })
}));

// The SSO page's own sections fetch from the API; they are not under test here.
vi.mock('./_components/sso-page-client', () => ({ default: () => <p>sso page</p> }));

const renderSection = (ssoEnabled: boolean) =>
    render(
        <RuntimeFlagsProvider flags={{ ssoEnabled }}>
            <SSOSectionLayout workspaceName="acme">
                <p>tab content</p>
            </SSOSectionLayout>
        </RuntimeFlagsProvider>
    );

describe('the Single sign-on section', () => {
    beforeEach(() => {
        pathname = '/acme/dashboard/sso';
        granted = [P.SECURITY_MANAGE];
        vi.mocked(redirect).mockClear();
    });
    afterEach(() => vi.unstubAllEnvs());

    it('shows Single sign-on, then Domains, when SSO is on', () => {
        renderSection(true);
        expect(screen.getByRole('navigation', { name: 'Single sign-on sections' })).toBeInTheDocument();
        expect(screen.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual(['/acme/dashboard/sso', '/acme/dashboard/sso/domains']);
        expect(screen.getByRole('link', { name: 'Single sign-on' })).toHaveAttribute('aria-current', 'page');
        expect(screen.getByRole('link', { name: 'Domains' })).not.toHaveAttribute('aria-current');
    });

    it('marks Domains as current on its own route', () => {
        pathname = '/acme/dashboard/sso/domains';
        renderSection(true);
        expect(screen.getByRole('link', { name: 'Domains' })).toHaveAttribute('aria-current', 'page');
        expect(screen.getByRole('link', { name: 'Single sign-on' })).not.toHaveAttribute('aria-current');
    });

    it('shows just the Domains page, without a tab bar, when SSO is off', () => {
        pathname = '/acme/dashboard/sso/domains';
        renderSection(false);
        expect(screen.queryByRole('navigation')).toBeNull();
        expect(screen.queryByText('Single sign-on')).toBeNull();
        expect(screen.getByText('tab content')).toBeInTheDocument();
    });

    it('shows no tabs to a member without security.manage', () => {
        granted = [P.FORM_READ];
        renderSection(true);
        expect(screen.queryByRole('navigation')).toBeNull();
    });

    it('sends /sso to the Domains tab when SSO is off on this instance', async () => {
        vi.stubEnv('SSO_ENABLED', '');
        await SsoPage({ params: Promise.resolve({ workspace_name: 'acme' }) });
        expect(redirect).toHaveBeenCalledWith('/acme/dashboard/sso/domains');
    });

    it('renders the Single sign-on tab when SSO is on', async () => {
        vi.stubEnv('SSO_ENABLED', 'true');
        render(await SsoPage({ params: Promise.resolve({ workspace_name: 'acme' }) }));
        expect(redirect).not.toHaveBeenCalled();
        expect(screen.getByText('sso page')).toBeInTheDocument();
    });
});
