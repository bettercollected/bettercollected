import React from 'react';

import { ExpandMore, SettingsOutlined } from '@mui/icons-material';
import { Accordion, AccordionDetails, AccordionSummary, Box, Divider, List, ListItem, Toolbar } from '@mui/material';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { DashboardIcon } from '@app/components/icons/dashboard-icon';
import { FormIcon } from '@app/components/icons/form-icon';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import { IDrawerProps, INavbarItem } from '@app/models/props/navbar';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { toEndDottedStr } from '@app/utils/stringUtils';

DashboardDrawer.defaultProps = {
    drawerWidth: 289,
    mobileOpen: false
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle }: IDrawerProps) {
    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetAllMineWorkspacesQuery();
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
            key: 'workspace-settings',
            name: 'Workspace Settings',
            url: `/${workspace?.workspaceName}/manage`,
            icon: SettingsOutlined
        }
    ];

    const drawer = (
        <>
            <Toolbar />
            <Box sx={{ overflow: 'auto', height: '100%' }}>
                <List>
                    <ListItem disablePadding>
                        <Accordion disabled={isLoading} sx={{ paddingY: '16px', paddingX: '4px', width: '100%' }} elevation={0} className="hover:bg-zinc-100">
                            <AccordionSummary expandIcon={<ExpandMore className="h-7 w-7 text-black-900 transition-all duration-300" />}>
                                <AuthAccountProfileImage image={workspace?.profileImage} name={workspace?.title} />
                                <p className="ml-3 p-0 !body1 flex items-center">{toEndDottedStr(workspace?.title, 30)}</p>
                            </AccordionSummary>
                            <AccordionDetails className="w-full flex flex-col gap-3">
                                {data && Array.isArray(data) && data.length > 1 ? (
                                    data.map((w) => <p key={w?.id}>{w?.title}</p>)
                                ) : (
                                    <p className="text-black-600">Currently, you only have a single workspace. Creation of new workspaces and collaboration coming soon.</p>
                                )}
                            </AccordionDetails>
                        </Accordion>
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
