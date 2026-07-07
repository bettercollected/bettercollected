// @ts-nocheck
import React from 'react';

import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import { IDrawerProps } from '@app/models/props/navbar';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import WorkspaceMenuDropdown from '@Components/workspace/workspace-menu-dropdown';

const Drawer = ({ navGroups, isAdmin }: any) => {
    return (
        <div className="flex flex-col h-full bg-white">
            {/* Top band matches the main navbar (77px + hairline border), with
                the workspace switcher vertically centred — so the sidebar top
                and the navbar read as one continuous bar. No product logo:
                the workspace's own identity leads; bettercollected keeps a
                quiet attribution at the very bottom instead. */}
            <div className="border-b-black-200 flex h-[77px] shrink-0 items-center border-b px-4">
                <WorkspaceMenuDropdown fullWidth />
            </div>
            <div className="flex-1 overflow-auto h-full scrollbar-hide">
                <div className="flex min-h-full flex-col justify-between">
                    <div className="px-4 pt-2">
                        {/* Nav grouped by meaning (Collection · Your site ·
                            Workspace), not by permission — the old split was
                            "everyone" vs "admins", which separated Site from
                            Site settings. Labels carry what dividers implied. */}
                        {navGroups?.map((group: any) => {
                            const items = group.items.filter((item: any) => !item.adminOnly || isAdmin);
                            if (!items.length) return null;
                            return (
                                <div key={group.label} className="pb-1">
                                    <div className="text-black-500 px-4 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider">{group.label}</div>
                                    <NavigationList navigationList={items} />
                                </div>
                            );
                        })}
                    </div>

                    {/* Attribution, not advertisement — the same quiet caption
                        the responder surfaces carry, in place of the old
                        upgrade upsell. */}
                    <div className="px-4 pb-6 pt-4">
                        <a href="https://bettercollected.com/" target="_blank" rel="noopener noreferrer" className="text-black-500 hover:text-black-700 flex items-center justify-center px-4 text-xs">
                            Powered by&nbsp;<span className="font-semibold">bettercollected</span>
                        </a>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle, navGroups }: IDrawerProps) {
    const isAdmin = useAppSelector(selectIsAdmin);

    return (
        <MuiDrawer handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen}>
            <Drawer navGroups={navGroups} isAdmin={isAdmin} />
        </MuiDrawer>
    );
}
