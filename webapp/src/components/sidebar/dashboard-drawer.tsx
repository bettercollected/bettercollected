import React from 'react';

import { Box, Divider, List, ListItem, Toolbar } from '@mui/material';

import { DashboardIcon } from '@app/components/icons/dashboard-icon';
import { FormIcon } from '@app/components/icons/form-icon';
import { SettingIcon } from '@app/components/icons/setting-icon';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import WorkspaceMenuDropdown from '@app/components/workspace/workspace-menu-dropdown';
import { IDrawerProps, INavbarItem } from '@app/models/props/navbar';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

DashboardDrawer.defaultProps = {
    drawerWidth: 289,
    mobileOpen: false
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle }: IDrawerProps) {
    const workspace = useAppSelector(selectWorkspace);
    const isAdmin = useAppSelector(selectIsAdmin);
    const commonWorkspaceUrl = `/${workspace?.workspaceName}/dashboard`;

    const topNavList: Array<INavbarItem> = [
        {
            key: 'dashboard',
            name: 'Dashboard',
            url: commonWorkspaceUrl,
            icon: DashboardIcon
        },
        {
            key: 'forms',
            name: 'Forms',
            url: `${commonWorkspaceUrl}/forms`,
            icon: FormIcon
        }
    ];
    const bottomNavList: Array<INavbarItem> = [
        {
            key: 'manage-workspace',
            name: 'Manage workspace',
            url: `/${workspace?.workspaceName}/manage`,
            icon: SettingIcon
        }
    ];

    const drawer = (
        <>
            <Toolbar />
            <Box sx={{ overflow: 'auto', height: '100%' }}>
                <List>
                    <ListItem disablePadding sx={{ paddingY: '20px', paddingX: '20px', width: '100%' }}>
                        <WorkspaceMenuDropdown fullWidth />
                    </ListItem>
                </List>
                <Divider />
                <NavigationList navigationList={topNavList} />
                {isAdmin && (
                    <>
                        <Divider />
                        <NavigationList navigationList={bottomNavList} />
                    </>
                )}
            </Box>
        </>
    );

    return (
        <>
            <MuiDrawer drawer={drawer} handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen} />
        </>
    );
}
