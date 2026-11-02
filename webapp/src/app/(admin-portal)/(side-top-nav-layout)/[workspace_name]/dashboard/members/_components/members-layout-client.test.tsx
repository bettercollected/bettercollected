// The Members page's tabs: Teams joins Collaborators and Pending requests only for owners and admins, and only
// while the server has form-level access on.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import MembersLayout from './members-layout-client';

const served = vi.hoisted(() => ({ enabled: true, admin: true }));

vi.mock('next/navigation', () => ({ usePathname: () => '/acme/dashboard/members/collaborators' }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ formAccessEnabled: served.enabled, can: (permission: string) => served.admin && permission === 'members.manage' })
}));

const tabs = () => screen.getAllByRole('link').map((link) => link.getAttribute('href')?.split('/').pop());

describe('the Members tabs', () => {
    beforeEach(() => {
        served.enabled = true;
        served.admin = true;
    });

    it('add Teams for an owner or admin while the switch is on, as a link to its own page', () => {
        render(
            <MembersLayout params={{ workspace_name: 'acme' }}>
                <p>content</p>
            </MembersLayout>
        );
        expect(tabs()).toContain('teams');
        expect(screen.getByRole('link', { name: /Teams/ })).toHaveAttribute('href', '/acme/dashboard/members/teams');
        expect(tabs()).toEqual(['collaborators', 'pending-requests', 'teams']);
    });

    it('have no Teams tab while the switch is off', () => {
        served.enabled = false;
        render(
            <MembersLayout params={{ workspace_name: 'acme' }}>
                <p>content</p>
            </MembersLayout>
        );
        expect(tabs()).not.toContain('teams');
        expect(tabs()).toHaveLength(2);
    });

    it('have no Teams tab for anyone who may not manage members', () => {
        served.admin = false;
        render(
            <MembersLayout params={{ workspace_name: 'acme' }}>
                <p>content</p>
            </MembersLayout>
        );
        expect(tabs()).not.toContain('teams');
    });
});
