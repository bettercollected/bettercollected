import React, { useState } from 'react';

import { useRouter } from 'next/router';

import Toolbar from '@Components/Common/Layout/Toolbar';
import { Share } from '@mui/icons-material';
import { Box, IconButton } from '@mui/material';

import CustomizeLink from '@app/components/cards/customizelink-card';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import SettingsDrawer from '@app/components/sidebar/settings-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import LinkView from '@app/components/ui/link-view';
import ShareView from '@app/components/ui/share-view';
import environments from '@app/configs/environments';
import { workspaceCustomizeLink } from '@app/constants/Customize-domain';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageWorkspaceLayout({ children }: any) {
    const workspace = useAppSelector(selectWorkspace);
    const [mobileOpen, setMobileOpen] = useState(false);
    const router = useRouter();
    const { openModal } = useModal();
    const isProPlan = useAppSelector(selectIsProPlan);
    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: 'Dashboard',
            url: `/${workspace?.workspaceName}/dashboard`
        },
        {
            title: 'Manage Workspace',
            disabled: true
        }
    ];
    const isCustomDomain = !!workspace.customDomain;
    const clientHostUrl = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}`;
    const customDomainUrl = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}`;
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };
    const handleClick = () => {
        if (!isProPlan) {
            router.push(`/${workspace.workspaceName}/upgrade`);
        } else {
            openModal('CUSTOMIZE_URL', { description: workspaceCustomizeLink.description, domain: isCustomDomain ? customDomainUrl : clientHostUrl });
        }
    };
    return (
        <SidebarLayout DrawerComponent={SettingsDrawer}>
            <div className=" relative">
                <div className="flex z-10 justify-between">
                    <div className=" flex h-[56px]  items-center space-x-4">
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
                            <ShareView url={clientHostUrl} showCopy={false} showBorder={false} title="Workspace" iconSize="small" />

                            <div className="mt-12">
                                <div className="body1 !leading-none mb-4">Workspace Url</div>
                                <LinkView url={isCustomDomain ? customDomainUrl : clientHostUrl} toastMessage="Workspace Url Copied" className="flex flex-col" />
                            </div>
                            <div className="my-12">
                                <CustomizeLink title={workspaceCustomizeLink.title} subtitle={workspaceCustomizeLink.description} buttonText={isProPlan ? 'Customize Link' : 'Upgrade TO PRO'} onClick={handleClick} />
                            </div>
                        </div>
                    </Box>
                </>
            </MuiDrawer>
        </SidebarLayout>
    );
}
