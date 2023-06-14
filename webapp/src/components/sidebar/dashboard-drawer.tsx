import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import DashboardIcon from '@Components/Common/Icons/Dashboard';
import DeleteIcon from '@Components/Common/Icons/Delete';
import { FormIcon } from '@Components/Common/Icons/FormIcon';
import MembersIcon from '@Components/Common/Icons/Members';
import ResponderIcon from '@Components/Common/Icons/Responder';
import Toolbar from '@Components/Common/Layout/Toolbar';
import { Box, LinearProgress, List, ListItem } from '@mui/material';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import WorkspaceMenuDropdown from '@app/components/workspace/workspace-menu-dropdown';
import { localesCommon } from '@app/constants/locales/common';
import dashboardConstants from '@app/constants/locales/dashboard';
import { formConstant } from '@app/constants/locales/form';
import { members } from '@app/constants/locales/members';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { IDrawerProps, INavbarItem } from '@app/models/props/navbar';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import { useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import Globe from '../icons/flags/globe';

DashboardDrawer.defaultProps = {
    drawerWidth: 289,
    mobileOpen: false
};

const Drawer = ({ topNavList, isAdmin, bottomNavList }: any) => {
    const { t } = useTranslation();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceStatsQuery(workspace.id);
    const { openModal } = useFullScreenModal();

    const isProPlan = useAppSelector(selectIsProPlan);

    return (
        <>
            <Toolbar />
            <Box sx={{ overflow: 'auto', height: '100%' }}>
                <div className="flex h-full flex-col justify-between">
                    <div>
                        <List disablePadding className={JOYRIDE_CLASS.WORKSPACE_SWITCHER}>
                            <ListItem disablePadding>
                                <WorkspaceMenuDropdown fullWidth />
                            </ListItem>
                        </List>
                        <Divider />
                        <NavigationList className={JOYRIDE_CLASS.WORKSPACE_NAVIGATION} sx={{ paddingY: '8px' }} navigationList={topNavList} />
                        {isAdmin && (
                            <>
                                <Divider />
                                <NavigationList className={JOYRIDE_CLASS.WORKSPACE_ADVANCE_NAVIGATION} sx={{ paddingY: '8px' }} navigationList={bottomNavList} />
                            </>
                        )}
                    </div>
                    {isAdmin && !isProPlan && (
                        <div>
                            <Divider className="pb-6" />
                            <div className="px-5 py-6">
                                <div
                                    className="body1 pb-3 hover:underline cursor-pointer font-medium"
                                    onClick={() => {
                                        openModal('UPGRADE_TO_PRO', { featureText: t(upgradeConst.features.unlimitedForms.slogan) });
                                    }}
                                >
                                    Upgrade To PRO
                                </div>
                                <div className="body4">for unlimited form import and many more features.</div>
                                <LinearProgress className="my-5 py-[2px]" variant="determinate" value={data?.forms || 0} color="inherit" />
                                <div className="body4">
                                    {data?.forms || 0}/100 {' forms imported'}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </Box>
        </>
    );
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle }: IDrawerProps) {
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    const commonWorkspaceUrl = `/${workspace?.workspaceName}/dashboard`;

    const topNavList: Array<INavbarItem> = [
        {
            key: 'dashboard',
            name: t(localesCommon.dashboard),
            url: commonWorkspaceUrl,
            icon: <DashboardIcon />
        },
        {
            key: 'forms',
            name: t(localesCommon.forms),
            url: `${commonWorkspaceUrl}/forms`,
            icon: <FormIcon />
        },
        {
            key: 'responders',
            name: t(localesCommon.respondersAndGroups),
            url: `${commonWorkspaceUrl}/responders`,
            icon: <ResponderIcon />
        },
        {
            key: 'deletion_requests',
            name: t(formConstant.deletionRequests),
            url: `${commonWorkspaceUrl}/deletion-requests`,
            icon: <DeleteIcon />
        }
    ];
    const bottomNavList: Array<INavbarItem> = [
        {
            key: 'members',
            name: t(members.default),
            url: `/${workspace?.workspaceName}/dashboard/members`,
            icon: <MembersIcon />
        },
        {
            key: 'urls',
            name: t(dashboardConstants.drawer.manageURLs),
            url: `/${workspace?.workspaceName}/dashboard/urls`,
            icon: <Globe />
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
