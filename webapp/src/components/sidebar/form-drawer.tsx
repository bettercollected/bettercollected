import React from 'react';

import Toolbar from '@Components/Common/Layout/Toolbar';
import { Box } from '@mui/material';

import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import { IDrawerProps, INavbarItem } from '@app/models/props/navbar';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function FormDrawer({ drawerWidth, mobileOpen, handleDrawerToggle }: IDrawerProps) {
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const commonUrl = `/${workspace?.workspaceName}/dashboard/forms/${form.formId}`;

    const navbarItems: Array<INavbarItem> = [
        {
            key: 'preview',
            name: 'Form Preview',
            url: commonUrl
        },
        {
            key: 'responses',
            name: 'Responses (' + (form.responses || 0) + ')',
            url: `${commonUrl}/responses`
        },
        {
            key: 'deletion_requests',
            name: 'Deletion Requests',
            url: `${commonUrl}/deletion-requests`
        },
        {
            key: 'settings',
            name: 'Settings',
            url: `${commonUrl}/settings`
        }
    ];

    return (
        <>
            <MuiDrawer handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen}>
                <Toolbar />
                <Box sx={{ overflow: 'auto', height: '100%' }}>
                    <NavigationList navigationList={navbarItems} />
                </Box>
            </MuiDrawer>
        </>
    );
}
