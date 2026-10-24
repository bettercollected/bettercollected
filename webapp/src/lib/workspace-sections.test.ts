// Which Single sign-on and AI tabs a member sees, and where AI opens.
import { describe, expect, it } from 'vitest';

import { WorkspacePermission as P } from '@app/models/enums/workspace-permission';

import { aiTabs, defaultAiTabUrl, isTabActive, ssoTabs, workspaceSectionUrls } from './workspace-sections';

const holding =
    (...permissions: Array<string>) =>
    (permission: string) =>
        permissions.includes(permission);

const OWNER = holding(P.MEMBERS_MANAGE, P.WORKSPACE_MANAGE, P.SECURITY_MANAGE, P.AI_MANAGE, P.FORM_READ);
const MEMBER = holding(P.FORM_READ, P.FORM_EDIT);
const AI_ADMIN = holding(P.AI_MANAGE);
const SECURITY_ADMIN = holding(P.SECURITY_MANAGE);

const keys = (tabs: Array<{ key: string }>) => tabs.map((tab) => tab.key);

describe('AI tabs', () => {
    it('shows an owner every tab, in order', () => {
        expect(keys(aiTabs('acme', OWNER))).toEqual(['profile', 'memory', 'mcp', 'settings']);
        expect(aiTabs('acme', OWNER).map((tab) => tab.href)).toEqual(['/acme/dashboard/ai/profile', '/acme/dashboard/ai/memory', '/acme/dashboard/ai/mcp', '/acme/dashboard/ai/settings']);
    });

    it.each([
        ['a plain member', MEMBER, ['memory', 'settings']],
        ['someone who manages AI', AI_ADMIN, ['profile', 'memory', 'settings']],
        ['someone who manages security', SECURITY_ADMIN, ['memory', 'mcp', 'settings']]
    ])('follows the permissions of %s', (_, can, expected) => {
        expect(keys(aiTabs('acme', can))).toEqual(expected);
    });

    it.each([
        ['an owner', OWNER, '/acme/dashboard/ai/profile'],
        ['someone who manages AI', AI_ADMIN, '/acme/dashboard/ai/profile'],
        ['someone who manages security', SECURITY_ADMIN, '/acme/dashboard/ai/memory'],
        ['a plain member', MEMBER, '/acme/dashboard/ai/memory']
    ])('opens on the first tab %s may use', (_, can, expected) => {
        expect(defaultAiTabUrl('acme', can)).toBe(expected);
    });
});

describe('Single sign-on tabs', () => {
    it('orders Single sign-on before Domains when SSO is on', () => {
        expect(keys(ssoTabs('acme', OWNER, true))).toEqual(['sso', 'domains']);
        expect(ssoTabs('acme', OWNER, true).map((tab) => tab.href)).toEqual(['/acme/dashboard/sso', '/acme/dashboard/sso/domains']);
    });

    it('leaves only Domains when SSO is off', () => {
        expect(keys(ssoTabs('acme', OWNER, false))).toEqual(['domains']);
    });

    it('needs security.manage for both tabs', () => {
        expect(ssoTabs('acme', MEMBER, true)).toEqual([]);
        expect(ssoTabs('acme', AI_ADMIN, true)).toEqual([]);
        expect(keys(ssoTabs('acme', SECURITY_ADMIN, true))).toEqual(['sso', 'domains']);
    });
});

describe('isTabActive', () => {
    const [sso, domains] = ssoTabs('acme', OWNER, true);

    it('matches the Single sign-on tab on its own path only', () => {
        expect(isTabActive('/acme/dashboard/sso', sso)).toBe(true);
        expect(isTabActive('/acme/dashboard/sso/', sso)).toBe(true);
        expect(isTabActive('/acme/dashboard/sso/domains', sso)).toBe(false);
        expect(isTabActive('/acme/dashboard/sso/domains', domains)).toBe(true);
    });

    it('matches nested paths of a tab without exact', () => {
        expect(isTabActive('/acme/dashboard/sso/domains/x', domains)).toBe(true);
        expect(isTabActive('/acme/dashboard/sso/domainsx', domains)).toBe(false);
        expect(isTabActive(null, domains)).toBe(false);
    });
});

describe('workspaceSectionUrls', () => {
    it('gives the new address of every page that became a tab', () => {
        expect(workspaceSectionUrls('acme')).toEqual({
            sso: '/acme/dashboard/sso',
            domains: '/acme/dashboard/sso/domains',
            ai: '/acme/dashboard/ai',
            aiProfile: '/acme/dashboard/ai/profile',
            aiMemory: '/acme/dashboard/ai/memory',
            aiMcp: '/acme/dashboard/ai/mcp',
            aiSettings: '/acme/dashboard/ai/settings'
        });
    });
});
