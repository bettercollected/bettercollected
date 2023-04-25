import React from 'react';

import { Box, Toolbar } from '@mui/material';

import { DashboardIcon } from '@app/components/icons/dashboard-icon';
import { FormIcon } from '@app/components/icons/form-icon';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import { IDrawerProps, INavbarItem } from '@app/models/props/navbar';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function SettingsDrawer({ drawerWidth, mobileOpen, handleDrawerToggle }: IDrawerProps) {
    const workspace = useAppSelector(selectWorkspace);
    const commonUrl = `/${workspace?.workspaceName}/manage`;

    const topNavList: Array<INavbarItem> = [
        {
            key: 'basic',
            name: 'Basic information',
            url: commonUrl
        },
        {
            key: 'members',
            name: 'Members',
            url: `${commonUrl}/members`
        },
        {
            key: 'advanced',
            name: 'Advanced Settings',
            url: `${commonUrl}/advanced`
        }
    ];

    const drawer = (
        <>
            <Toolbar />
            <Box sx={{ overflow: 'auto', height: '100%' }}>
                <NavigationList navigationList={topNavList} />
            </Box>
        </>
    );

    return (
        <>
            <MuiDrawer drawer={drawer} handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen} />
        </>
    );
}
