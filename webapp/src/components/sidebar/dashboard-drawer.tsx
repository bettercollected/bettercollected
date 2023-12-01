import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import DeleteIcon from '@Components/Common/Icons/Common/Delete';
import DashboardIcon from '@Components/Common/Icons/Dashboard/Dashboard';
import MembersIcon from '@Components/Common/Icons/Dashboard/Members';
import ResponderIcon from '@Components/Common/Icons/Dashboard/Responder';
import { FormIcon } from '@Components/Common/Icons/Form/FormIcon';
import { Box, LinearProgress, List, ListItem } from '@mui/material';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import Logo from '@app/components/ui/logo';
import WorkspaceMenuDropdown from '@app/components/workspace/workspace-menu-dropdown';
import { localesCommon } from '@app/constants/locales/common';
import dashboardConstants from '@app/constants/locales/dashboard';
import { formConstant } from '@app/constants/locales/form';
import { members } from '@app/constants/locales/members';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { toolTipConstant } from '@app/constants/locales/tooltip';
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
    const { data } = useGetWorkspaceStatsQuery(workspace.id, { skip: !workspace.id });
    const { openModal } = useFullScreenModal();

    const isProPlan = useAppSelector(selectIsProPlan);

    return (
        <>
            <div className="px-10 pt-6">
                <Logo isCustomDomain={false} isFooter={false} isClientDomain={false} />
            </div>
            <Box sx={{ overflow: 'auto', height: '100%' }}>
                <div className="flex h-full flex-col justify-between">
                    <div className="px-4">
                        <List disablePadding sx={{ paddingY: '20px' }} className={JOYRIDE_CLASS.WORKSPACE_SWITCHER}>
                            <ListItem disablePadding>
                                <WorkspaceMenuDropdown fullWidth />
                            </ListItem>
                        </List>
                        <NavigationList className={JOYRIDE_CLASS.WORKSPACE_NAVIGATION} sx={{ paddingY: '8px' }} navigationList={topNavList} />
                        {isAdmin && (
                            <>
                                <Divider className="text-black-600" />
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
                                    {t(pricingPlan.title)}
                                </div>
                                <div className="body4">{t(pricingPlan.forUnlimitedForms)}</div>
                                <LinearProgress className="my-5 py-[2px]" variant="determinate" value={data?.forms || 0} color="inherit" />
                                <div className="body4">
                                    {data?.forms || 0}/100 {' ' + t(toolTipConstant.formImported)}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </Box>
        </>
    );
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle, bottomNavList, topNavList }: IDrawerProps) {
    const isAdmin = useAppSelector(selectIsAdmin);

    return (
        <>
            <MuiDrawer handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen}>
                <Drawer topNavList={topNavList} isAdmin={isAdmin} bottomNavList={bottomNavList} />
            </MuiDrawer>
        </>
    );
}
