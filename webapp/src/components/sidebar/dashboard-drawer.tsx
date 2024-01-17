import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import styled from '@emotion/styled';
import { Box, LinearProgress, List, ListItem } from '@mui/material';
import { linearProgressClasses } from '@mui/material/LinearProgress';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import Logo from '@app/components/ui/logo';
import WorkspaceMenuDropdown from '@app/components/workspace/workspace-menu-dropdown';
import environments from '@app/configs/environments';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { IDrawerProps } from '@app/models/props/navbar';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import { useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

DashboardDrawer.defaultProps = {
    drawerWidth: 289,
    mobileOpen: false
};

const BorderLinearProgress = styled(LinearProgress)({
    height: 10,
    borderRadius: 5,
    [`&.${linearProgressClasses.colorPrimary}`]: {
        backgroundColor: '#FFFFFF'
    },
    [`& .${linearProgressClasses.bar}`]: {
        borderRadius: 5,
        backgroundColor: '#0764EB'
    }
});

const Drawer = ({ topNavList, isAdmin, bottomNavList }: any) => {
    const { t } = useTranslation();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceStatsQuery(workspace.id, { skip: !workspace.id });
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const { openModal } = useModal();
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
                            <div className="rounded-md mx-2 mb-4 bg-new-white-200 p-4">
                                <div className="h5-new mb-2">{t(pricingPlan.title)}</div>
                                <div className="text-black-600 text-sm">For unlimited forms and many more features</div>
                                <BorderLinearProgress className="mt-4 mb-2 text-black-500" variant="determinate" value={data?.forms || 0} color="inherit" />
                                <div className="text-xs font-semibold flex items-center justify-between">
                                    <span className="text-black-800">
                                        {data?.forms || 0}/100 {' ' + t(toolTipConstant.formImported)}
                                    </span>
                                    <span
                                        className="text-brand-500 cursor-pointer hover:underline"
                                        onClick={() => {
                                            openFullScreenModal('UPGRADE_TO_PRO', { featureText: t(upgradeConst.features.unlimitedForms.slogan) });
                                        }}
                                    >
                                        {t('BUTTON.UPGRADE')}
                                    </span>
                                </div>
                            </div>
                            <div className="rounded-md mx-2 mb-6 bg-new-white-200 p-4">
                                <div className="h5-new mb-2">Pro Lifetime Deal</div>
                                <div className="text-black-600 text-sm">
                                    Redeem{' '}
                                    <a href={environments.APP_SUMO_PRODUCT_URL} target="_blank" rel="noreferrer" className="text-black-800 underline cursor-pointer">
                                        AppSumo code
                                    </a>{' '}
                                    to get a lifetime pro account.
                                </div>
                                <div className="text-xs font-semibold flex items-center justify-end">
                                    <span
                                        className="text-brand-500 cursor-pointer hover:underline"
                                        onClick={() => {
                                            openModal('REDEEM_CODE_MODAL');
                                        }}
                                    >
                                        Redeem Code
                                    </span>
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
