import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import DashboardIcon from '@Components/Common/Icons/Dashboard';
import DeleteIcon from '@Components/Common/Icons/Delete';
import { FormIcon } from '@Components/Common/Icons/FormIcon';
import MembersIcon from '@Components/Common/Icons/Members';
import ResponderIcon from '@Components/Common/Icons/Responder';
import { Box } from '@mui/material';
import cn from 'classnames';
import { AnimatePresence, motion } from 'framer-motion';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import AuthNavbar from '@app/components/auth/navbar';
import Globe from '@app/components/icons/flags/globe';
import { TemplateIcon } from '@app/components/icons/template';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import DashboardDrawer from '@app/components/sidebar/dashboard-drawer';
import LocaleDropdownUi from '@app/components/ui/locale-dropdown-ui';
import { localesCommon } from '@app/constants/locales/common';
import dashboardConstants from '@app/constants/locales/dashboard';
import { formConstant } from '@app/constants/locales/form';
import { members } from '@app/constants/locales/members';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { INavbarItem } from '@app/models/props/navbar';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface ISidebarLayout {
    children: any;
    DrawerComponent?: any;
    boxClassName?: string;
}

export default function SidebarLayout({ children, DrawerComponent = DashboardDrawer, boxClassName = '' }: ISidebarLayout) {
    const drawerWidth = 289;

    const { openModal } = useFullScreenModal();

    const [mobileOpen, setMobileOpen] = React.useState(false);
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    const router = useRouter();

    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const commonWorkspaceUrl = `/${workspace?.workspaceName}/dashboard`;

    const topNavList: Array<INavbarItem> = [
        {
            key: 'dashboard',
            name: t('MY_WORKSPACE'),
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
            url: `${commonWorkspaceUrl}/responders-groups`,
            icon: <ResponderIcon />
        },
        {
            key: 'deletion_requests',
            name: t(formConstant.deletionRequests),
            url: `${commonWorkspaceUrl}/deletion-requests`,
            icon: <DeleteIcon className="stroke-2" />
        },
        {
            key: 'templates',
            name: t('TEMPLATE.TEMPLATES'),
            url: `${commonWorkspaceUrl}/templates`,
            icon: <TemplateIcon className={'stroke-2'} />
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
            url: ``,
            icon: <Globe />,
            onClick: () => {
                openModal('WORKSPACE_SETTINGS', { initialIndex: 1 });
            }
        }
    ];

    const allNavList = [...topNavList, ...bottomNavList];

    const getHeader = () => {
        const matchingNavList = allNavList.filter((item) => router.asPath.includes(item.url));
        if (matchingNavList.length > 0) {
            return matchingNavList[matchingNavList.length - 1].name;
        }
        return 'My Workspace';
    };

    return (
        <AnimatePresence mode="wait" initial={true} onExitComplete={() => window.scrollTo(0, 0)}>
            <div className="relative min-h-screen w-full">
                <div className="lg:hidden">
                    <AuthNavbar handleDrawerToggle={handleDrawerToggle} mobileOpen={mobileOpen} />
                </div>
                <DrawerComponent drawerWidth={drawerWidth} mobileOpen={mobileOpen} handleDrawerToggle={handleDrawerToggle} topNavList={topNavList} bottomNavList={bottomNavList} />
                <Box className={`float-none lg:float-right lg:min-h-screen bg-black-100 min-h-calc-68 mt-[68px] lg:mt-0`} component="main" sx={{ display: 'flex', width: { lg: `calc(100% - ${drawerWidth}px)` } }}>
                    <div className="flex flex-col w-full">
                        <div className="flex w-full py-3 z-[1000] sticky top-[68px] lg:top-0 bg-white justify-between px-5 border-b border-b-black-200 lg:px-10 items-center">
                            <span className="h3-new">{getHeader()}</span>
                            <div className="hidden lg:flex gap-4">
                                <LocaleDropdownUi />
                                <AuthAccountMenuDropdown hideMenu={false} isClientDomain={false} />
                            </div>
                        </div>
                        <motion.div
                            initial={{ x: 0, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            exit={{ x: 300, opacity: 0 }}
                            transition={{
                                ease: 'linear',
                                duration: 0.5,
                                x: { duration: 0.5 }
                            }}
                            className={cn(`w-full h-full`)}
                        >
                            <div className={cn('w-full h-full bg-black-100', boxClassName)}>{children}</div>
                        </motion.div>
                    </div>
                </Box>
            </div>
        </AnimatePresence>
    );
}
