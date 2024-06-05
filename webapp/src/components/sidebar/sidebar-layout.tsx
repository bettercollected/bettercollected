import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import DeleteIcon from '@Components/Common/Icons/Common/Delete';
import MembersIcon from '@Components/Common/Icons/Dashboard/Members';
import ResponderIcon from '@Components/Common/Icons/Dashboard/Responder';
import { FormIcon } from '@Components/Common/Icons/Form/FormIcon';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { Box } from '@mui/material';
import cn from 'classnames';
import { AnimatePresence, motion } from 'framer-motion';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import AuthNavbar from '@app/components/auth/navbar';
import Globe from '@app/components/icons/flags/globe';
import { TemplateIcon } from '@app/components/icons/template';
import DashboardDrawer from '@app/components/sidebar/dashboard-drawer';
import LocaleDropdownUi from '@app/components/ui/locale-dropdown-ui';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { members } from '@app/constants/locales/members';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { INavbarItem } from '@app/models/props/navbar';
import { Popover, PopoverContent } from '@app/shadcn/components/ui/popover';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { PopoverTrigger } from '@radix-ui/react-popover';
import HelpMenuComponent from './HelpMenuComponent';
import HelpMenuItem from './HelpMenuItem';
import { ProLogo } from '../ui/logo';
import { useFullScreenModal } from '../modal-views/full-screen-modal-context';

interface ISidebarLayout {
    children: any;
    DrawerComponent?: any;
    boxClassName?: string;
}

export default function SidebarLayout({ children, DrawerComponent = DashboardDrawer, boxClassName = '' }: ISidebarLayout) {
    const drawerWidth = 289;

    const auth = useAppSelector(selectAuth);

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
        }
    ];
    auth?.roles?.includes('ADMIN') &&
        topNavList.push({
            key: 'templates',
            name: t('TEMPLATE.TEMPLATES'),
            url: `${commonWorkspaceUrl}/templates`,
            icon: <TemplateIcon className={'stroke-2'} />
        });
    const bottomNavList: Array<INavbarItem> = [
        {
            key: 'members',
            name: t(members.default),
            url: `/${workspace?.workspaceName}/dashboard/members`,
            icon: <MembersIcon />
        },

        {
            key: 'custom-domain',
            name: (
                <div className="flex items-center gap-2">
                    Custom Domain <ProLogo />
                </div>
            ),
            icon: <Globe />,
            url: `/${workspace?.workspaceName}/dashboard/custom-domain`,
            onClick: () => {
                if (workspace.isPro) {
                    router.push(`/${workspace?.workspaceName}/dashboard/custom-domain`);
                } else {
                    openModal('UPGRADE_TO_PRO');
                }
            }
        }
    ];

    const allNavList = [...topNavList, ...bottomNavList];

    const getHeader = () => {
        const matchingNavList = allNavList.filter((item) => router.asPath.includes(item.url));
        if (matchingNavList.length > 0) {
            return matchingNavList[matchingNavList.length - 2]?.name;
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
                <Box className={`bg-black-100 min-h-calc-68 float-none mt-[68px] lg:float-right lg:mt-0 lg:min-h-screen`} component="main" sx={{ display: 'flex', width: { lg: `calc(100% - ${drawerWidth}px)` } }}>
                    <div className="flex w-full flex-col">
                        <div className="border-b-black-200 sticky top-[68px] z-[1000] flex w-full items-center justify-between border-b bg-white px-5 py-3 lg:top-0 lg:px-10">
                            <span className="h3-new">{getHeader()}</span>
                            <div className="hidden gap-4 lg:flex lg:items-center">
                                <Popover>
                                    <PopoverTrigger>
                                        <HelpMenuComponent />
                                    </PopoverTrigger>
                                    <PopoverContent side="bottom" align="end" asChild className="!z-[2000] w-fit rounded-2xl p-0">
                                        <div className="bg-white  p-2 ">
                                            <HelpMenuItem />
                                        </div>
                                    </PopoverContent>
                                </Popover>
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
                            className={cn(`h-full w-full`)}
                        >
                            <div className={cn('bg-black-100 h-full w-full', boxClassName)}>{children}</div>
                        </motion.div>
                    </div>
                </Box>
            </div>
        </AnimatePresence>
    );
}
