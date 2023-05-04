import React, { useState } from 'react';

import { useRouter } from 'next/router';

import Toolbar from '@Components/Common/Layout/Toolbar';
import { Share } from '@mui/icons-material';
import { Box, IconButton } from '@mui/material';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { Close } from '@app/components/icons/close';
import SettingsDrawer from '@app/components/sidebar/settings-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import environments from '@app/configs/environments';
import { workspaceCustomizeLink } from '@app/constants/Customize-link';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import CustomizeLink from '../cards/customizelink-card';
import MuiDrawer from '../sidebar/mui-drawer';
import LinkView from '../ui/link-view';
import ShareView from '../ui/share-view';

export default function ManageWorkspaceLayout({ children }: any) {
    const workspace = useAppSelector(selectWorkspace);
    const [mobileOpen, setMobileOpen] = useState(false);
    const router = useRouter();
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
        }
    };
    return (
        <SidebarLayout DrawerComponent={SettingsDrawer}>
            <div className="py-5 relative">
                <div className="flex z-10 justify-between">
                    <div className=" flex  items-center space-x-4">
                        <BreadcrumbsRenderer items={breadcrumbsItem} />
                    </div>
                    <div onClick={handleDrawerToggle}>
                        <IconButton>
                            <Share />
                        </IconButton>
                    </div>
                </div>
                <div className="absolute lg:left-[-40px] px-5 lg:px-10 pb-10 mt-16 top-0 w-full xl:max-w-289-calc-289">{children}</div>
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
                        <div className=" px-5 h-full py-6 relative w-full">
                            <Close onClick={handleDrawerToggle} className="absolute blocks lg:hidden right-5 top-5 cursor-pointer" />
                            <ShareView url={clientHostUrl} showCopy={false} showBorder={false} title="Workspace" iconSize="small" />

                            <div className="mt-12">
                                <div className="body1 !leading-none">Workspace Url</div>
                                <LinkView url={isCustomDomain ? customDomainUrl : clientHostUrl} toastMessage="Workspace Url Copied" />
                            </div>
                            <div className="my-12">
                                <CustomizeLink title={workspaceCustomizeLink.title} subtitle={workspaceCustomizeLink.subtitle} buttonText={isProPlan ? 'Customize Link' : 'Upgrade TO PRO'} onClick={handleClick} />
                            </div>
                        </div>
                    </Box>
                </>
            </MuiDrawer>
        </SidebarLayout>
    );
}
