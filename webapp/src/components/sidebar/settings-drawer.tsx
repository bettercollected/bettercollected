import React from 'react';

import { useTranslation } from 'next-i18next';

import Toolbar from '@Components/Common/Layout/Toolbar';
import { Box } from '@mui/material';

import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import { advanceSetting, localesDefault, members, workspaceConstant } from '@app/constants/locales';
import { IDrawerProps, INavbarItem } from '@app/models/props/navbar';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function SettingsDrawer({ drawerWidth, mobileOpen, handleDrawerToggle }: IDrawerProps) {
    const workspace = useAppSelector(selectWorkspace);
    const commonUrl = `/${workspace?.workspaceName}/manage`;
    const { t } = useTranslation();

    const navbarItems: Array<INavbarItem> = [
        {
            key: 'basic',
            name: t(workspaceConstant.manage),
            url: commonUrl
        },
        {
            key: 'members',
            name: t(members.member),
            url: `${commonUrl}/members`
        },
        {
            key: 'advanced',
            name: t(advanceSetting.default),
            url: `${commonUrl}/advanced`
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
