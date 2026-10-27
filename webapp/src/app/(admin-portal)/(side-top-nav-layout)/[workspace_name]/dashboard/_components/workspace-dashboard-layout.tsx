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
import ResponderIcon from '@Components/icons/responder';
import HelpMenuComponent from '@Components/sidebar/help-menu-component';
import HelpMenuItem from '@Components/sidebar/help-menu-item';
import { Settings, Trash2 } from 'lucide-react';
import { useWorkspaceSettingsView } from '@app/store/jotai/workspace-settings-view';

import AuthNavbar from '@app/components/auth/auth-navbar';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useSsoEnabled } from '@app/shared/hocs/runtime-flags-provider';
import { INavGroup, INavbarItem } from '@app/models/props/navbar';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import DashboardDrawer from '@Components/sidebar/dashboard-drawer';
import { workspaceNavItems } from '@Components/sidebar/workspace-nav-items';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { navItemForPath } from '@app/lib/nav-items';
import { useRegistrationEnabled } from '@app/components/registration/use-registration-enabled';

const WorkspaceDashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const ssoEnabled = useSsoEnabled();
    const { can } = useWorkspacePermissions();
    const { enabled: registrationEnabled } = useRegistrationEnabled();
    const drawerWidth = 289;

    const auth = useAppSelector(selectAuth);
    const { openModal } = useFullScreenModal();
    const { settingsViewOpen, setSettingsViewOpen } = useWorkspaceSettingsView();

    const [mobileOpen, setMobileOpen] = React.useState(false);
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    const router = useRouter();
    const pathname = usePathname();

    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const commonWorkspaceUrl = `/${workspace?.workspaceName}/dashboard`;

    // Nav grouped by meaning: the daily work first (Linear-style), then the
    // public face, then administration.
    const collectionItems: Array<INavbarItem> = [
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
            // responders are privacy.manage, responder groups form.edit
            anyPermission: [WorkspacePermission.PRIVACY_MANAGE, WorkspacePermission.FORM_EDIT],
            icon: <ResponderIcon />
        },
        {
            key: 'deletion_requests',
            name: t(formConstant.deletionRequests),
            url: `${commonWorkspaceUrl}/deletion-requests`,
            permission: WorkspacePermission.PRIVACY_MANAGE,
            icon: <Trash2 className="stroke-2" />
        }
    ];

    if (auth?.roles?.includes('ADMIN')) {
        collectionItems.push({
            key: 'templates',
            name: t('TEMPLATE.TEMPLATES'),
            url: `${commonWorkspaceUrl}/templates`,
            icon: <TemplateIcon className={'stroke-2'} />
        });
    }

    const navGroups: Array<INavGroup> = [
        {
            label: 'Collection',
            items: collectionItems
        },
        {
            label: 'Your site',
            items: [
                {
                    key: 'site',
                    name: 'Site',
                    url: commonWorkspaceUrl,
                    // The dashboard root prefixes every other route (exact
                    // match only) — and when the settings view covers the
                    // mirror, the highlight belongs to Site settings.
                    exactMatch: true,
                    isActive: pathname === commonWorkspaceUrl && !settingsViewOpen,
                    icon: <Globe />,
                    // Clicking Site returns to the page even when the settings
                    // view (which lives on the same route) is open.
                    onClick: () => {
                        setSettingsViewOpen(false);
                        router.push(commonWorkspaceUrl);
                    }
                },
                {
                    key: 'site-settings',
                    // Settings live inside the site frame (behind the
                    // address-bar gear) — this entry opens that view directly.
                    name: 'Site settings',
                    url: `${commonWorkspaceUrl}/site-settings`,
                    // saved through the workspace PATCH (workspace.manage)
                    permission: WorkspacePermission.WORKSPACE_MANAGE,
                    // Not a route — active while its view is open on the root.
                    isActive: pathname === commonWorkspaceUrl && settingsViewOpen,
                    icon: <Settings className="h-5 w-5 stroke-2" />,
                    onClick: () => {
                        setSettingsViewOpen(true);
                        router.push(commonWorkspaceUrl);
                    }
                },
                {
                    key: 'custom-domain',
                    name: (
                        <div className="flex items-center gap-2">
                            Custom domain <ProLogo />
                        </div>
                    ),
                    icon: <Globe />,
                    url: `${commonWorkspaceUrl}/custom-domain`,
                    // setting the domain is the workspace PATCH (workspace.manage)
                    permission: WorkspacePermission.WORKSPACE_MANAGE,
                    onClick: () => {
                        if (workspace?.isPro) {
                            router.push(`${commonWorkspaceUrl}/custom-domain`);
                        } else {
                            openModal('UPGRADE_TO_PRO');
                        }
                    }
                }
            ]
        },
        {
            label: 'Workspace',
            items: workspaceNavItems({ workspaceName: workspace?.workspaceName, t, can, ssoEnabled, registrationEnabled })
        }
    ];

    const allNavList = navGroups.flatMap((group) => group.items);

    const getHeader = () => {
        if (!pathname) return 'My Workspace';
        // Longest matching path wins (lib/nav-items.ts): the Site item's URL
        // (the dashboard root) is a prefix of every other route, and a
        // section such as AI titles every one of its tabs.
        const current = navItemForPath(pathname, allNavList);
        if (current) {
            return current.key === 'site' ? (settingsViewOpen ? 'Site settings' : 'Your site') : current.name;
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
            <DashboardDrawer drawerWidth={drawerWidth} mobileOpen={mobileOpen} handleDrawerToggle={handleDrawerToggle} navGroups={navGroups} />
            <main
                className={cn(
                    "bg-black-100 float-none mt-[68px] flex min-h-[calc(100vh-68px)]",
                    "lg:float-right lg:mt-0 lg:min-h-screen lg:w-[calc(100%-289px)]"
                )}
            >
                <div className="flex w-full flex-col">
                    <div className="border-b-black-400 sticky top-[68px] z-1000 flex w-full items-center justify-between border-b bg-white px-5 py-3 lg:top-0 lg:px-10">
                        <span className="h3-new">{getHeader()}</span>
                        <div className="hidden gap-4 lg:flex lg:items-center">
                            <Popover>
                                <PopoverTrigger asChild>
                                    <div className="cursor-pointer">
                                        <HelpMenuComponent />
                                    </div>
                                </PopoverTrigger>
                                <PopoverContent side="bottom" align="end" className="w-fit rounded p-0">
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
