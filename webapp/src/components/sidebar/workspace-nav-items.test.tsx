// The sidebar's Workspace group: order per role, the SSO flag, and which item
// is active (and titles the page) on every tab of a section.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { isNavItemActive, navItemForPath, visibleNavItems } from '@app/lib/nav-items';
import { WorkspacePermission as P } from '@app/models/enums/workspace-permission';

import NavigationList from './navigation-list';
import { workspaceNavItems } from './workspace-nav-items';

let pathname = '/acme/dashboard';
const push = vi.fn();
vi.mock('next/navigation', () => ({ usePathname: () => pathname, useRouter: () => ({ push, prefetch: vi.fn() }) }));

const LABELS: Record<string, string> = {
    'MEMBERS.DEFAULT': 'Members',
    'WORKSPACE_SECTIONS.THEMES': 'Themes',
    'WORKSPACE_SECTIONS.SSO': 'Single sign-on',
    'WORKSPACE_SECTIONS.DOMAINS': 'Domains',
    'WORKSPACE_SECTIONS.AI': 'AI'
};
const t = (key: string) => LABELS[key] ?? key;

const holding =
    (...permissions: Array<string>) =>
    (permission: string) =>
        permissions.includes(permission);
const OWNER = holding(...Object.values(P));
const MEMBER = holding(P.FORM_READ, P.FORM_EDIT, P.FORM_CREATE, P.RESPONSE_READ);

const visible = (can: (p: string) => boolean, ssoEnabled = true) => visibleNavItems(workspaceNavItems({ workspaceName: 'acme', t, can, ssoEnabled }), can);
const names = (items: Array<{ name: React.ReactNode }>) => items.map((item) => item.name);

describe('the Workspace group', () => {
    beforeEach(() => {
        pathname = '/acme/dashboard';
        push.mockClear();
    });

    it('shows an owner Members, Themes, Single sign-on and AI, in that order', () => {
        expect(names(visible(OWNER))).toEqual(['Members', 'Themes', 'Single sign-on', 'AI']);
    });

    it('shows a member without manage permissions only AI, opening on Memory', () => {
        const items = visible(MEMBER);
        expect(names(items)).toEqual(['AI']);
        expect(items[0].url).toBe('/acme/dashboard/ai/memory');
    });

    it('opens AI on Profile for someone who manages AI', () => {
        const ai = visible(OWNER).find((item) => item.key === 'ai');
        expect(ai?.url).toBe('/acme/dashboard/ai/profile');
    });

    it('keeps each item behind the permission it had', () => {
        expect(names(visible(holding(P.SECURITY_MANAGE)))).toEqual(['Single sign-on', 'AI']);
        expect(names(visible(holding(P.MEMBERS_MANAGE)))).toEqual(['Members', 'AI']);
        expect(names(visible(holding(P.WORKSPACE_MANAGE)))).toEqual(['Themes', 'AI']);
    });

    it('opens Single sign-on on its own tab when SSO is on', () => {
        const sso = visible(OWNER, true)[2];
        expect(sso).toMatchObject({ key: 'sso', name: 'Single sign-on', url: '/acme/dashboard/sso' });
    });

    it('names the third item Domains and opens the verified domains when SSO is off', () => {
        const items = visible(OWNER, false);
        expect(names(items)).toEqual(['Members', 'Themes', 'Domains', 'AI']);
        expect(items[2]).toMatchObject({ key: 'domains', url: '/acme/dashboard/sso/domains' });
        expect(names(items)).not.toContain('Single sign-on');
    });

    it.each([
        ['/acme/dashboard/ai/profile', 'AI'],
        ['/acme/dashboard/ai/memory', 'AI'],
        ['/acme/dashboard/ai/mcp', 'AI'],
        ['/acme/dashboard/ai/settings', 'AI'],
        ['/acme/dashboard/sso', 'Single sign-on'],
        ['/acme/dashboard/sso/domains', 'Single sign-on'],
        ['/acme/dashboard/members/pending-requests', 'Members'],
        ['/acme/dashboard/themes', 'Themes']
    ])('titles %s with %s and keeps that item active', (path, name) => {
        const items = workspaceNavItems({ workspaceName: 'acme', t, can: OWNER, ssoEnabled: true });
        const site = { key: 'site', name: 'Site', url: '/acme/dashboard', exactMatch: true };
        expect(navItemForPath(path, [site, ...items])?.name).toBe(name);
        expect(items.filter((item) => isNavItemActive(path, item)).map((item) => item.name)).toEqual([name]);
        expect(isNavItemActive(path, site)).toBe(false);
    });

    it('titles the Domains page "Domains" when SSO is off', () => {
        const items = workspaceNavItems({ workspaceName: 'acme', t, can: OWNER, ssoEnabled: false });
        expect(navItemForPath('/acme/dashboard/sso/domains', items)?.name).toBe('Domains');
    });

    it('does not light up AI on a route that merely starts with the same letters', () => {
        const items = workspaceNavItems({ workspaceName: 'acme', t, can: OWNER, ssoEnabled: true });
        expect(items.filter((item) => isNavItemActive('/acme/dashboard/ai-settings', item))).toEqual([]);
    });

    it('renders the items in order and highlights AI on its Memory tab', () => {
        pathname = '/acme/dashboard/ai/memory';
        render(<NavigationList navigationList={visible(OWNER)} />);
        const rows = screen.getAllByRole('listitem');
        expect(rows.map((row) => row.textContent)).toEqual(['Members', 'Themes', 'Single sign-on', 'AI']);
        expect(rows[3]).toHaveClass('bg-brand-100', 'font-medium');
        expect(rows.slice(0, 3).some((row) => row.classList.contains('bg-brand-100'))).toBe(false);
    });
});
