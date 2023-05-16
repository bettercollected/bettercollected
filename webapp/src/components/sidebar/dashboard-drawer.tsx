import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import Toolbar from '@Components/Common/Layout/Toolbar';
import Joyride from '@Components/Joyride';
import { Box, List, ListItem } from '@mui/material';

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

const Drawer = ({ topNavList, isAdmin, bottomNavList }: any) => {
    return (
        <>
            <Toolbar />
            <Box sx={{ overflow: 'auto', height: '100%' }}>
                <List disablePadding className="joyride-workspace-switcher">
                    <ListItem disablePadding>
                        <WorkspaceMenuDropdown fullWidth />
                    </ListItem>
                </List>
                <Divider />
                <NavigationList className="joyride-workspace-navigations" sx={{ paddingY: '20px' }} navigationList={topNavList} />
                {isAdmin && (
                    <>
                        <Divider />
                        <NavigationList className="joyride-workspace-settings" navigationList={bottomNavList} />
                    </>
                )}
            </Box>
        </>
    );
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
            icon: <DashboardIcon />
        },
        {
            key: 'forms',
            name: 'Forms',
            url: `${commonWorkspaceUrl}/forms`,
            icon: <FormIcon />
        }
    ];
    const bottomNavList: Array<INavbarItem> = [
        {
            key: 'manage-workspace',
            name: 'Manage workspace',
            url: `/${workspace?.workspaceName}/manage`,
            icon: <SettingIcon />
        }
    ];

    return (
        <>
            <Joyride
                id="workspace-admin-dashboard-drawer"
                scrollOffset={0}
                steps={[
                    {
                        title: <span className="sh3">Your workspace</span>,
                        content: <p className="body4">This is your current active workspace. You can switch to other workspaces, or create your own new personal workspace from here.</p>,
                        target: '.joyride-workspace-switcher'
                    },
                    {
                        title: <span className="sh3">Workspace navigations</span>,
                        content: <p className="body4">Using these navigation links, you can navigate to your imported forms, responses, and deletion requests.</p>,
                        target: '.joyride-workspace-navigations'
                    },
                    {
                        title: <span className="sh3">Advance navigations</span>,
                        content: <p className="body4">Using these navigation links, you can navigate to workspace settings, update your workspace, manage members, and many more.</p>,
                        target: '.joyride-workspace-settings'
                    }
                ]}
            />
            <MuiDrawer handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen}>
                <Drawer topNavList={topNavList} isAdmin={isAdmin} bottomNavList={bottomNavList} />
            </MuiDrawer>
        </>
    );
}
