// The sidebar drawer: one labelled navigation landmark around the groups, and the phone drawer closing once a
// route change follows an activated item.
import React from 'react';

import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { INavGroup } from '@app/models/props/navbar';

import DashboardDrawer from './dashboard-drawer';
import MuiDrawer from './mui-drawer';

let pathname = '/acme/dashboard/forms';
let isMobile = false;
vi.mock('next/navigation', () => ({ usePathname: () => pathname, useRouter: () => ({ push: vi.fn(), prefetch: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-breakpoint', () => ({ useIsMobile: () => isMobile }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => true }) }));
vi.mock('@Components/workspace/workspace-menu-dropdown', () => ({ default: () => <div data-testid="workspace-switcher" /> }));

const groups: Array<INavGroup> = [
    { label: 'Collection', items: [{ key: 'forms', name: 'Forms', url: '/acme/dashboard/forms' }] },
    { label: 'Workspace', items: [{ key: 'members', name: 'Members', url: '/acme/dashboard/members' }] }
];

beforeEach(() => {
    pathname = '/acme/dashboard/forms';
    isMobile = false;
});
afterEach(cleanup);

describe('the sidebar landmark', () => {
    it('is one navigation named "Workspace menu", apart from the "Workspace" group label, holding every group', () => {
        render(<DashboardDrawer drawerWidth={289} mobileOpen={false} handleDrawerToggle={vi.fn()} navGroups={groups} />);
        const navs = screen.getAllByRole('navigation');
        expect(navs).toHaveLength(1);
        expect(navs[0]).toHaveAccessibleName('Workspace menu');
        expect(within(navs[0]).getAllByRole('link').map((link) => link.textContent)).toEqual(['Forms', 'Members']);
    });
});

describe('the phone drawer', () => {
    it('is asked to close when the route changes while it is open, and not when it merely opens', () => {
        isMobile = true;
        const close = vi.fn();
        const drawer = (open: boolean) => (
            <MuiDrawer drawerWidth={289} mobileOpen={open} handleDrawerToggle={close}>
                <button type="button">Members</button>
            </MuiDrawer>
        );
        const { rerender } = render(drawer(false));
        rerender(drawer(true));
        expect(close).not.toHaveBeenCalled();
        // following an item (a link or a button that pushes) changes the path: that is what closes the sheet
        pathname = '/acme/dashboard/members';
        rerender(drawer(true));
        expect(close).toHaveBeenCalledTimes(1);
    });
});
