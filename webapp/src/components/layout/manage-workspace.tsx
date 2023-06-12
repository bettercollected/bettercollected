import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Toolbar from '@Components/Common/Layout/Toolbar';
import { Share } from '@mui/icons-material';
import { Box, IconButton } from '@mui/material';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { Close } from '@app/components/icons/close';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import SettingsDrawer from '@app/components/sidebar/settings-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import LinkView from '@app/components/ui/link-view';
import ShareView from '@app/components/ui/share-view';
import environments from '@app/configs/environments';
import { breadcrumbsItems } from '@app/constants/locales/breadcrumbs-items';
import { toastMessage } from '@app/constants/locales/toast-message';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageWorkspaceLayout({ children }: any) {
    const workspace = useAppSelector(selectWorkspace);
    const [mobileOpen, setMobileOpen] = useState(false);
    const { t } = useTranslation();
    const router = useRouter();
    const locale = router?.locale === 'en' ? '' : `${router?.locale}/`;
    const isProPlan = useAppSelector(selectIsProPlan);
    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(breadcrumbsItems.dashboard),
            url: `/${locale}${workspace?.workspaceName}/dashboard`
        },
        {
            title: t(breadcrumbsItems.manageWorkspace),
            disabled: true
        }
    ];
    const isCustomDomain = !!workspace.customDomain;
    const clientHostUrl = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}`;
    const customDomainUrl = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}`;
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };
    // const handleClick = () => {
    //     if (!isProPlan) {
    //         router.push(`/${workspace.workspaceName}/upgrade`);
    //     } else {
    //         openModal('CUSTOMIZE_URL', { description: t(customize.domainDescription), domain: isCustomDomain ? customDomainUrl : clientHostUrl });
    //     }
    // };
    return (
        <SidebarLayout DrawerComponent={SettingsDrawer}>
            <div className=" relative">
                <div className="flex z-10 justify-between">
                    <div className=" flex   items-center space-x-4">
                        <BreadcrumbsRenderer items={breadcrumbsItem} />
                    </div>
                    <div onClick={handleDrawerToggle}>
                        <IconButton>
                            <Share />
                        </IconButton>
                    </div>
                </div>
                <div className="absolute lg:left-[-40px] px-5 lg:px-10 pb-10 mt-[73px] top-0 w-full xl:max-w-289-calc-289">{children}</div>
            </div>
            <MuiDrawer
                mobileOpen={mobileOpen}
                anchor="right"
                handleDrawerToggle={handleDrawerToggle}
                mobileDrawerDisplayProps={{ xs: 'block', sm: 'block', md: 'block', lg: 'block', xl: 'none' }}
                desktopDrawerDisplayProps={{ xs: 'none', sm: 'none', md: 'none', lg: 'none', xl: 'block' }}
            >
                <>
                    <Toolbar />
                    <Box sx={{ overflow: 'auto', height: '100%' }}>
                        <div className=" px-5 h-full py-8 relative w-full">
                            <Close onClick={handleDrawerToggle} className="absolute blocks lg:hidden right-5 top-5 cursor-pointer" />
                            <ShareView url={clientHostUrl} showCopy={false} showBorder={false} title={t(workspaceConstant.share)} iconSize="small" />

                            <div className="mt-12">
                                <div className="body1 !leading-none mb-4">{t(workspaceConstant.url)}</div>
                                <LinkView url={isCustomDomain ? customDomainUrl : clientHostUrl} toastMessage={t(toastMessage.workspaceUrlCopied)} className="flex flex-col" buttonClassName="!text-brand-500 !border-blue-200 hover:!bg-brand-200 " />
                            </div>
                            {/* <div className="my-12">
                                <CustomizeLink title={t(customize.domain)} subtitle={t(customize.domainDescription)} buttonText={isProPlan ? t(buttonConstant.customizeLink) : t(buttonConstant.upgradeToPro)} onClick={handleClick} />
                            </div> */}
                        </div>
                    </Box>
                </>
            </MuiDrawer>
        </SidebarLayout>
    );
}
