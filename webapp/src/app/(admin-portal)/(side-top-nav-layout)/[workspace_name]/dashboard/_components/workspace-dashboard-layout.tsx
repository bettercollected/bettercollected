"use client";

import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { usePathname, useRouter } from 'next/navigation';
import React from 'react';
import { useTranslation } from 'react-i18next';

import AuthAccountMenuDropdown from '@app/components/auth/account-menu-dropdown';
import Globe from '@app/components/icons/flags/globe';
import { TemplateIcon } from '@app/components/icons/template';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { ProLogo } from '@app/components/ui/logo';
import { FormIcon } from '@Components/icons/form-icon';
import MembersIcon from '@Components/icons/members';
import ResponderIcon from '@Components/icons/responder';
import HelpMenuComponent from '@Components/sidebar/help-menu-component';
import HelpMenuItem from '@Components/sidebar/help-menu-item';
import { Trash2 } from 'lucide-react';

import AuthNavbar from '@app/components/auth/auth-navbar';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { members } from '@app/constants/locales/members';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { INavbarItem } from '@app/models/props/navbar';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import DashboardDrawer from '@Components/sidebar/dashboard-drawer';

const WorkspaceDashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const drawerWidth = 289;

    const auth = useAppSelector(selectAuth);
    const { openModal } = useFullScreenModal();

    const [mobileOpen, setMobileOpen] = React.useState(false);
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    const router = useRouter();
    const pathname = usePathname();

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
            icon: <Trash2 className="stroke-2" />
        }
    ];

    if (auth?.roles?.includes('ADMIN')) {
        topNavList.push({
            key: 'templates',
            name: t('TEMPLATE.TEMPLATES'),
            url: `${commonWorkspaceUrl}/templates`,
            icon: <TemplateIcon className={'stroke-2'} />
        });
    }

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
                if (workspace?.isPro) {
                    router.push(`/${workspace?.workspaceName}/dashboard/custom-domain`);
                } else {
                    openModal('UPGRADE_TO_PRO');
                }
            }
        }
    ];

    const allNavList = [...topNavList, ...bottomNavList];

    const getHeader = () => {
        if (!pathname) return 'My Workspace';
        const matchingNavList = allNavList.filter((item) => pathname?.includes(item.url));
        if (matchingNavList.length > 0) {
            return matchingNavList[matchingNavList.length - 1]?.name;
        }
        // Routes not represented in the sidebar nav still need a correct title.
        if (pathname.includes('/dashboard/templates')) return 'Templates';
        if (pathname.includes('/dashboard/account-settings')) return 'Account Settings';
        return 'My Workspace';
    };

    return (
        <div className="relative min-h-screen w-full">
            <div className="lg:hidden">
                <AuthNavbar showHamburgerIcon handleDrawerToggle={handleDrawerToggle} mobileOpen={mobileOpen} showAuthAccount />
            </div>
            <DashboardDrawer
                drawerWidth={drawerWidth}
                mobileOpen={mobileOpen}
                handleDrawerToggle={handleDrawerToggle}
                topNavList={topNavList}
                bottomNavList={bottomNavList}
            />
            <main
                className={cn(
                    "bg-black-100 float-none mt-[68px] flex min-h-[calc(100vh-68px)]",
                    "lg:float-right lg:mt-0 lg:min-h-screen lg:w-[calc(100%-289px)]"
                )}
            >
                <div className="flex w-full flex-col">
                    <div className="border-b-black-200 sticky top-[68px] z-[1000] flex w-full items-center justify-between border-b bg-white px-5 py-3 lg:top-0 lg:px-10">
                        <span className="h3-new">{getHeader()}</span>
                        <div className="hidden gap-4 lg:flex lg:items-center">
                            <Popover>
                                <PopoverTrigger asChild>
                                    <div className="cursor-pointer">
                                        <HelpMenuComponent />
                                    </div>
                                </PopoverTrigger>
                                <PopoverContent side="bottom" align="end" className="!z-[2000] w-fit rounded-2xl p-0">
                                    <div className="bg-white  p-2 ">
                                        <HelpMenuItem />
                                    </div>
                                </PopoverContent>
                            </Popover>
                            {/* <LocaleDropdownUiApp /> */}
                            <AuthAccountMenuDropdown hideMenu={false} isClientDomain={false} />
                        </div>
                    </div>

                    <div
                        className={cn('bg-black-100 h-full w-full px-5 lg:px-10 pt-10')}
                    >
                        {children}
                    </div>
                </div>
            </main>
        </div>
    );
};

export default WorkspaceDashboardLayout;
