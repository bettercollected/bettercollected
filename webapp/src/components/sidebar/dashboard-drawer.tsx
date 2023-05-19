import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import DashboardIcon from '@Components/Common/Icons/Dashboard';
import DeleteIcon from '@Components/Common/Icons/Delete';
import { FormIcon } from '@Components/Common/Icons/FormIcon';
import MembersIcon from '@Components/Common/Icons/Members';
import ResponderIcon from '@Components/Common/Icons/Responder';
import SettingsIcon from '@Components/Common/Icons/Settings';
import Toolbar from '@Components/Common/Layout/Toolbar';
import { Box, List, ListItem } from '@mui/material';

import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import WorkspaceMenuDropdown from '@app/components/workspace/workspace-menu-dropdown';
import { formsConstant } from '@app/constants/locales/forms';
import { localesGlobal } from '@app/constants/locales/global';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { IDrawerProps, INavbarItem } from '@app/models/props/navbar';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
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
                <List disablePadding className={JOYRIDE_CLASS.WORKSPACE_SWITCHER}>
                    <ListItem disablePadding>
                        <WorkspaceMenuDropdown fullWidth />
                    </ListItem>
                </List>
                <Divider />
                <NavigationList className={JOYRIDE_CLASS.WORKSPACE_NAVIGATION} sx={{ paddingY: '20px' }} navigationList={topNavList} />
                {isAdmin && (
                    <>
                        <Divider />
                        <NavigationList className={JOYRIDE_CLASS.WORKSPACE_ADVANCE_NAVIGATION} navigationList={bottomNavList} />
                    </>
                )}
            </Box>
        </>
    );
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle }: IDrawerProps) {
    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    const commonWorkspaceUrl = `/${workspace?.workspaceName}/dashboard`;

    const topNavList: Array<INavbarItem> = [
        {
            key: 'dashboard',
            name: t(localesGlobal.dashboard),
            url: commonWorkspaceUrl,
            icon: <DashboardIcon height="24px" width="24px" />
        },
        {
            key: 'forms',
            name: t(formsConstant.default),
            url: `${commonWorkspaceUrl}/forms`,
            icon: <FormIcon />
        },
        {
            key: 'responders',
            name: 'Responders',
            url: `${commonWorkspaceUrl}/responders`,
            icon: <ResponderIcon />
        },
        {
            key: 'deletion_requests',
            name: 'Deletion Requests',
            url: `${commonWorkspaceUrl}/deletion-requests`,
            icon: <DeleteIcon />
        }
    ];
    const bottomNavList: Array<INavbarItem> = [
        {
            key: 'collaborators',
            name: 'Collaborators',
            url: `/${workspace?.workspaceName}/manage/members`,
            icon: <MembersIcon />
        },
        {
            key: 'manage-workspace',
            name: t(workspaceConstant.manage),
            url: `/${workspace?.workspaceName}/manage`,
            icon: <SettingsIcon />
        }
    ];

    return (
        <>
            <MuiDrawer handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen}>
                <Drawer topNavList={topNavList} isAdmin={isAdmin} bottomNavList={bottomNavList} />
            </MuiDrawer>
        </>
    );
}
