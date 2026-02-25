'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import { useTranslation } from 'react-i18next';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationListApp from '@app/components/sidebar/NavigationListApp';
import Logo from '@app/components/ui/logo';
import WorkspaceMenuDropdown from '@app/components/Workspace/workspace-menu-dropdown';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { IDrawerProps } from '@app/models/props/navbar';
import { Progress } from '@app/shadcn/components/ui/progress';
import { cn } from '@app/shadcn/util/lib';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import Globe from '@app/views/atoms/Icons/Flags/Globe';
import Divider from '@Components/common/divider';

const GradientBgDiv = ({ className, children }: { className?: string, children: React.ReactNode }) => (
    <div
        className={className}
        style={{
            background: 'linear-gradient(90.01deg, #0764eb 0.01%, #fe3678 101.52%)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            color: 'transparent'
        }}
    >
        {children}
    </div>
);

interface DashboardDrawerProps extends IDrawerProps {
    className?: string;
}

const DrawerContent = ({ topNavList, bottomNavList }: { topNavList: any[], bottomNavList: any[] }) => {
    const { t } = useTranslation();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceStatsQuery(workspace?.id || '', { skip: !workspace?.id });
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const { openModal } = useModal();
    const isAdmin = useAppSelector(selectIsAdmin);
    const isProPlan = useAppSelector(selectIsProPlan);
    const pathname = usePathname();
    const commonWorkspaceUrl = `/${workspace?.workspaceName}/dashboard`;

    return (
        <div className="flex flex-col h-full bg-white">
            <div className="px-10 pt-6">
                <Logo isCustomDomain={false} isFooter={false} isClientDomain={false} />
            </div>
            <div className="flex-1 overflow-auto h-full scrollbar-hide">
                <div className="flex h-full flex-col justify-between">
                    <div className="px-4">
                        <div className="pt-5 pb-0">
                            <WorkspaceMenuDropdown fullWidth />
                        </div>

                        <Link href={commonWorkspaceUrl} className={cn('hover:bg-slate-100 mb-3 mt-2 flex cursor-pointer items-center gap-2 rounded-xl px-4 py-3 text-xs  font-medium group', pathname === commonWorkspaceUrl && 'bg-slate-100')}>
                            <Globe width={20} height={20} className="text-blue-600" />
                            <GradientBgDiv className="p3-new">Public Workspace</GradientBgDiv>
                        </Link>

                        <div className="my-3 border-t border-gray-200" />

                        <div className="py-2">
                            <NavigationListApp navigationList={topNavList} />
                        </div>

                        {isAdmin && (
                            <>
                                <Divider className="text-black-600" />
                                <div className="py-2">
                                    <NavigationListApp navigationList={bottomNavList} />
                                </div>
                            </>
                        )}
                    </div>

                    {isAdmin && !isProPlan && (
                        <div className="mt-4 pb-4">
                            <div className="bg-slate-50 mx-4 mb-4 rounded-md p-4">
                                <div className="h5-new mb-2">{t(pricingPlan.title)}</div>
                                <div className="text-black-600 text-sm">For unlimited forms and many more features</div>

                                <Progress
                                    className="mb-2 mt-4 h-2.5 bg-white border border-gray-100"
                                    value={data?.forms || 0}
                                    indicatorColor="#0764EB"
                                />

                                <div className="flex items-center justify-between text-xs font-semibold mt-2">
                                    <span className="text-black-800">
                                        {data?.forms || 0}/100 {' ' + t(toolTipConstant.formImported)}
                                    </span>
                                    <span
                                        className="cursor-pointer hover:underline text-blue-600"
                                        onClick={() => {
                                            openFullScreenModal('UPGRADE_TO_PRO', { featureText: t(upgradeConst.features.unlimitedForms.slogan) });
                                        }}
                                    >
                                        {t('BUTTON.UPGRADE')}
                                    </span>
                                </div>
                            </div>

                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle, topNavList, bottomNavList }: DashboardDrawerProps) {
    return (
        <MuiDrawer handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen}>
            <DrawerContent topNavList={topNavList} bottomNavList={bottomNavList} />
        </MuiDrawer>
    );
}
