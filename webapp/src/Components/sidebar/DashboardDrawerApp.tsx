'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import Divider from '@Components/Common/DataDisplay/Divider';
import styled from '@emotion/styled';
import { Box, LinearProgress, List, ListItem } from '@mui/material';
import { linearProgressClasses } from '@mui/material/LinearProgress';
import { useModal } from '@app/Components/modal-views/context';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import MuiDrawer from '@app/Components/sidebar/mui-drawer';
import NavigationListApp from '@app/Components/sidebar/NavigationListApp';
import LogoApp from '@app/Components/ui/LogoApp';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsProPlan, selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import Globe from '@app/views/atoms/Icons/Flags/Globe';
import Link from 'next/link';
import { cn } from '@app/shadcn/util/lib';
import { usePathname } from 'next/navigation';
import Logo from '@Components/ui/logo';
import WorkspaceMenuDropdown from '@Components/Workspace/workspace-menu-dropdown';

const GradientBgDiv = styled.div`
    background: linear-gradient(90.01deg, #0764eb 0.01%, #fe3678 101.52%);
    background-clip: text;
`;

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
    const { data } = useGetWorkspaceStatsQuery(workspace?.id || '', { skip: !workspace?.id });
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const isProPlan = useAppSelector(selectIsProPlan);
    const pathname = usePathname();
    const commonWorkspaceUrl = `/${workspace?.workspaceName}/dashboard`;

    return (
        <>
            <div className="px-10 pt-6">
                <Logo isCustomDomain={false} isFooter={false} isClientDomain={false} />
            </div>
            <Box sx={{ overflow: 'auto', height: '100%' }}>
                <div className="flex h-full flex-col justify-between">
                    <div className="px-4">
                        <List disablePadding sx={{ paddingTop: '20px' }}>
                            <ListItem disablePadding>
                                <WorkspaceMenuDropdown fullWidth />
                            </ListItem>
                        </List>

                        <Link href={commonWorkspaceUrl} className={cn('hover:bg-black-100 mb-3 mt-2 flex cursor-pointer items-center gap-2 rounded-xl px-4 py-3 text-xs  font-medium text-transparent', pathname === commonWorkspaceUrl && 'bg-black-200')}>
                            <Globe width={20} height={20} className="text-blue-600" />
                            <GradientBgDiv className="p3-new">Public Workspace</GradientBgDiv>
                        </Link>
                        <hr className="mt-3" />
                        <NavigationListApp sx={{ paddingY: '8px' }} navigationList={topNavList} />
                        {isAdmin && (
                            <>
                                <Divider className="text-black-600" />
                                <NavigationListApp sx={{ paddingY: '8px' }} navigationList={bottomNavList} />
                            </>
                        )}
                    </div>
                    {isAdmin && !isProPlan && (
                        <div>
                            <div className="bg-new-white-200 mx-2 mb-4 rounded-md p-4">
                                <div className="h5-new mb-2">{t(pricingPlan.title)}</div>
                                <div className="text-black-600 text-sm">For unlimited forms and many more features</div>
                                <BorderLinearProgress className="text-black-500 mb-2 mt-4" variant="determinate" value={data?.forms || 0} color="inherit" />
                                <div className="flex items-center justify-between text-xs font-semibold">
                                    <span className="text-black-800">
                                        {data?.forms || 0}/100 {' ' + t(toolTipConstant.formImported)}
                                    </span>
                                </div>
                                <button
                                    onClick={() => openFullScreenModal('UPGRADE_TO_PRO')}
                                    className="mt-4 w-full rounded-md bg-blue-600 py-2 text-xs font-semibold text-white transition-colors hover:bg-blue-700"
                                >
                                    {t('UPGRADE_TO_PRO')}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </Box>
        </>
    );
};

export default function DashboardDrawerApp({ mobileOpen, handleDrawerToggle, drawerWidth, topNavList, bottomNavList }: any) {
    const isAdmin = useAppSelector(selectIsAdmin);
    return (
        <MuiDrawer
            mobileOpen={mobileOpen}
            handleDrawerToggle={handleDrawerToggle}
            drawerWidth={drawerWidth}
        >
            <Drawer topNavList={topNavList} isAdmin={isAdmin} bottomNavList={bottomNavList} />
        </MuiDrawer>
    );
}
