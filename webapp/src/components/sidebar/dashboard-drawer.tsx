// @ts-nocheck
import React from 'react';

import { useTranslation } from 'next-i18next';


import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import NavigationList from '@app/components/sidebar/navigation-list';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { IDrawerProps } from '@app/models/props/navbar';
import { Progress } from '@app/shadcn/components/ui/progress';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import WorkspaceMenuDropdown from '@Components/workspace/workspace-menu-dropdown';

const Drawer = ({ navGroups, isAdmin }: any) => {
    const { t } = useTranslation();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceStatsQuery(workspace.id, { skip: !workspace.id });
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const { openModal } = useModal();
    const isProPlan = useAppSelector(selectIsProPlan);

    return (
        <div className="flex flex-col h-full bg-white">
            <div className="px-10 pt-6">
                <Logo isCustomDomain={false} isFooter={false} isClientDomain={false} />
            </div>
            <div className="flex-1 overflow-auto h-full scrollbar-hide">
                <div className="flex h-full flex-col justify-between">
                    <div className="px-4">
                        <div className="pt-5 pb-2">
                            <WorkspaceMenuDropdown fullWidth />
                        </div>

                        {/* Nav grouped by meaning (Collection · Your site ·
                            Workspace), not by permission — the old split was
                            "everyone" vs "admins", which separated Site from
                            Site settings. Labels carry what dividers implied. */}
                        {navGroups?.map((group: any) => {
                            const items = group.items.filter((item: any) => !item.adminOnly || isAdmin);
                            if (!items.length) return null;
                            return (
                                <div key={group.label} className="pb-1">
                                    <div className="text-black-500 px-4 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider">{group.label}</div>
                                    <NavigationList navigationList={items} />
                                </div>
                            );
                        })}
                    </div>

                    {/* Bottom section for free plan / ads */}
                    {isAdmin && !isProPlan && (
                        <div className="mt-4 pb-4">
                            <div className="bg-black-100 mx-4 mb-4 rounded-md p-4">
                                <div className="h5-new mb-2">{t(pricingPlan.title)}</div>
                                <div className="text-black-600 text-sm">For unlimited forms and many more features</div>

                                <Progress
                                    className="border-black-200 mb-2 mt-4 h-2.5 border bg-white"
                                    value={data?.forms || 0}
                                    indicatorColor="#2456CC"
                                />

                                <div className="flex items-center justify-between text-xs font-semibold mt-2">
                                    <span className="text-black-800">
                                        {data?.forms || 0}/100 {' ' + t(toolTipConstant.formImported)}
                                    </span>
                                    <span
                                        className="cursor-pointer hover:underline text-[#2456CC]"
                                        onClick={() => {
                                            openFullScreenModal('UPGRADE_TO_PRO', { featureText: t(upgradeConst.features.unlimitedForms.slogan) });
                                        }}
                                    >
                                        {t('BUTTON.UPGRADE')}
                                    </span>
                                </div>
                            </div>

                            {environments.ENABLE_COUPON_CODES && (
                                <div className="bg-black-100 mx-4 mb-6 rounded-md p-4">
                                    <div className="h5-new mb-2">Pro Lifetime Deal</div>
                                    <div className="text-black-600 text-sm">
                                        Redeem{' '}
                                        <a href={environments.APP_SUMO_PRODUCT_URL} target="_blank" rel="noreferrer" className="text-black-800 cursor-pointer underline">
                                            AppSumo code
                                        </a>{' '}
                                        to get a lifetime pro account.
                                    </div>

                                    <div className="flex items-center justify-end text-xs font-semibold mt-2">
                                        <span
                                            className="cursor-pointer hover:underline text-[#2456CC]"
                                            onClick={() => {
                                                openModal('REDEEM_CODE_MODAL');
                                            }}
                                        >
                                            Redeem Code
                                        </span>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default function DashboardDrawer({ drawerWidth, mobileOpen, handleDrawerToggle, navGroups }: IDrawerProps) {
    const isAdmin = useAppSelector(selectIsAdmin);

    return (
        <MuiDrawer handleDrawerToggle={handleDrawerToggle} drawerWidth={drawerWidth} mobileOpen={mobileOpen}>
            <Drawer navGroups={navGroups} isAdmin={isAdmin} />
        </MuiDrawer>
    );
}
