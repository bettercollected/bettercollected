// The AI section: tabs per permission, the current tab, and where /ai opens.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission as P } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';

import AISectionLayout from './_components/ai-section-layout';
import AIPage from './page';

let pathname = '/acme/dashboard/ai/memory';
const replace = vi.fn();
vi.mock('next/navigation', () => ({
    usePathname: () => pathname,
    useParams: () => ({ workspace_name: 'acme' }),
    useRouter: () => ({ replace, push: vi.fn(), prefetch: vi.fn() })
}));

let granted: Array<string> = [];
let ready = true;
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => granted.includes(permission), ready, isLoading: !ready })
}));

const OWNER = [P.MEMBERS_MANAGE, P.WORKSPACE_MANAGE, P.SECURITY_MANAGE, P.AI_MANAGE];

const renderSection = () =>
    render(
        <AISectionLayout workspaceName="acme">
            <p>tab content</p>
        </AISectionLayout>
    );

const tabNames = () => screen.getAllByRole('link').map((link) => link.getAttribute('href')?.split('/').pop());

describe('the AI section', () => {
    beforeEach(() => {
        pathname = '/acme/dashboard/ai/memory';
        granted = [];
        ready = true;
        replace.mockClear();
    });

    it('shows an owner Profile, Memory, MCP and Settings in a nav named "AI sections"', () => {
        granted = OWNER;
        renderSection();
        expect(screen.getByRole('navigation', { name: 'AI sections' })).toBeInTheDocument();
        expect(tabNames()).toEqual(['profile', 'memory', 'mcp', 'settings']);
        for (const [name, path] of [
            ['Profile', 'profile'],
            ['Memory', 'memory'],
            ['MCP', 'mcp'],
            ['Settings', 'settings']
        ]) {
            expect(screen.getByRole('link', { name })).toHaveAttribute('href', `/acme/dashboard/ai/${path}`);
        }
        expect(screen.getByText('tab content')).toBeInTheDocument();
    });

    it('shows a plain member only Memory and Settings', () => {
        renderSection();
        expect(tabNames()).toEqual(['memory', 'settings']);
        expect(screen.queryByRole('link', { name: 'Profile' })).toBeNull();
        expect(screen.queryByRole('link', { name: 'MCP' })).toBeNull();
    });

    it.each([
        [[P.AI_MANAGE], ['profile', 'memory', 'settings']],
        [[P.SECURITY_MANAGE], ['memory', 'mcp', 'settings']]
    ])('follows the permissions %o', (permissions, expected) => {
        granted = permissions;
        renderSection();
        expect(tabNames()).toEqual(expected);
    });

    it('marks the open tab with aria-current="page"', () => {
        granted = OWNER;
        pathname = '/acme/dashboard/ai/mcp';
        renderSection();
        expect(screen.getByRole('link', { name: 'MCP' })).toHaveAttribute('aria-current', 'page');
        expect(screen.getAllByRole('link').filter((link) => link.getAttribute('aria-current') === 'page')).toHaveLength(1);
    });

    it('holds the tabs back until the permissions have arrived', () => {
        granted = OWNER;
        ready = false;
        renderSection();
        expect(screen.queryByRole('navigation')).toBeNull();
        expect(screen.getByText('tab content')).toBeInTheDocument();
    });

    it.each([
        ['an owner', OWNER, '/acme/dashboard/ai/profile'],
        ['someone who manages AI', [P.AI_MANAGE], '/acme/dashboard/ai/profile'],
        ['someone who manages security only', [P.SECURITY_MANAGE], '/acme/dashboard/ai/memory'],
        ['a plain member', [], '/acme/dashboard/ai/memory']
    ])('/ai opens %s on the first tab they may use', (_, permissions, target) => {
        granted = permissions;
        pathname = '/acme/dashboard/ai';
        render(<AIPage />);
        expect(replace).toHaveBeenCalledWith(target);
    });

    it('/ai waits for the permissions before choosing a tab', () => {
        ready = false;
        pathname = '/acme/dashboard/ai';
        render(<AIPage />);
        expect(replace).not.toHaveBeenCalled();
    });
});
