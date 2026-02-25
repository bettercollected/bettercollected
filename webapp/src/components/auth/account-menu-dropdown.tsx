"use client";
import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';


import Billing from '@app/components/Common/Icons/Dashboard/Billing';
import DashboardIcon from '@app/components/Common/Icons/Dashboard/Dashboard';

import WorkspaceAdminSelector from '@app/components/HOCs/WorkspaceAdminSelector';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useGetStatusQuery } from '@app/store/auth/api';
import { setAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ChevronRight, LogOut, Settings } from 'lucide-react';

interface IAuthAccountMenuDropdownProps {
    isClientDomain?: boolean;
    fullWidth?: boolean;
    hideMenu?: boolean;
    className?: string;
    menuContent?: React.ReactNode | React.ReactNode[];
    showExpandMore?: boolean;
}

AuthAccountMenuDropdown.defaultProps = {
    isClientDomain: false,
    fullWidth: false,
    hideMenu: false,
    className: '',
    menuContent: undefined,
    showExpandMore: undefined
};
export default function AuthAccountMenuDropdown({ isClientDomain, fullWidth, hideMenu, className, showExpandMore, menuContent }: IAuthAccountMenuDropdownProps) {
    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const { data } = useGetStatusQuery();
    const user = data ?? null;

    useEffect(() => {
        if (user && user?.id) {
            dispatch(setAuth({ ...user, isAdmin: workspace?.ownerId == user.id }));
        }
    }, [user?.id]);

    // const authStatus = useAppSelector(selectAuth);
    // const user: UserStatus = authStatus ?? null;

    const screenSize = useBreakpoint();
    const { openModal } = useModal();
    const [open, setOpen] = useState(false);

    const handleLogout = () => {
        setOpen(false);
        openModal('LOGOUT_VIEW', { workspace, isClientDomain: isClientDomain });
    };

    if (user?.isLoading) return <div className="bg-black-300 h-9 w-9 animate-pulse rounded-[4px] sm:w-32" />;
    if ((!user?.isLoading && !user?.id) || hideMenu) return null;

    const profileName = user?.firstName || user?.lastName ? _.capitalize(user?.firstName) + ' ' + _.capitalize(user?.lastName) : null;

    const newMenuContent = menuContent ?? (
        <>
            <AuthAccountProfileImage size={['xs', '2xs'].indexOf(screenSize) === -1 ? 36 : 28} image={user?.profileImage} name={user?.firstName || user?.lastName || user.email} />
            {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && (profileName?.trim() || user?.email || '')}
        </>)
    const shouldShowExpandMore = showExpandMore ?? ['xs', '2xs', 'sm'].indexOf(screenSize) === -1;

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <div
                    className={`${fullWidth ? 'w-full' : 'w-fit'} flex cursor-pointer items-center justify-between gap-2 rounded p-2 hover:rounded hover:bg-brand-100 body3 ${className}`}
                    id="account-menu"
                    role="button"
                    title={t(profileMenu.accountSettings)}
                >
                    <span className="flex items-center gap-2">{newMenuContent}</span>
                    {shouldShowExpandMore && (
                        <div className={`${open ? '!rotate-180' : '!-rotate-0'} transition-all duration-300`}>
                            <ChevronRight />
                        </div>
                    )}
                </div>
            </PopoverTrigger>
            <PopoverContent
                className="w-full min-w-[289px] p-0 z-[999999] bg-white"
                align="end"
                onClick={() => setOpen(false)}
                onInteractOutside={() => setOpen(false)}
            >
                <ul className="list-none m-0 p-0">
                    <li className="flex items-center px-5 py-3 hover:bg-brand-100 gap-4">
                        <div className="m-0">
                            <AuthAccountProfileImage size={40} image={user?.profileImage} name={profileName ?? ''} />
                        </div>
                        <div className="flex flex-col m-0">
                            <span className="text-[16px] leading-[24px] text-[#212529] font-normal">{profileName ?? 'Signed in as'}</span>
                            <span className="text-[12px] leading-[20px] text-[#6C757D] font-normal">{user?.email}</span>
                        </div>
                    </li>
                    <WorkspaceAdminSelector>
                        <li className="list-none">
                            <Separator className="my-2" />
                        </li>
                        {isClientDomain && (
                            <li className="list-none">
                                <ActiveLink
                                    href={`${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN.includes('localhost') ? 'http://' : 'https://'}${window?.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard`}
                                    referrerPolicy="no-referrer"
                                >
                                    <div className="flex items-center gap-4 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer">
                                        <div className="text-black-900 flex items-center justify-center">
                                            <DashboardIcon width={20} height={20} />
                                        </div>
                                        <span>{t(profileMenu.myDashboard)}</span>
                                    </div>
                                </ActiveLink>
                            </li>
                        )}
                        {user.stripeCustomerId && (
                            <li className="list-none">
                                <ActiveLink href={`${environments.API_ENDPOINT_HOST}/stripe/session/create/portal`} referrerPolicy="no-referrer">
                                    <div className="flex items-center gap-4 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer">
                                        <div className="text-black-900 flex items-center justify-center">
                                            <Billing width={20} height={20} />
                                        </div>
                                        <span>{t(profileMenu.billing)}</span>
                                    </div>
                                </ActiveLink>
                            </li>
                        )}
                    </WorkspaceAdminSelector>
                    <li className="list-none">
                        <ActiveLink
                            href={`${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN.includes('localhost') ? 'http://' : 'https://'}${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/account-settings`}
                            referrerPolicy="no-referrer"
                        >
                            <div className="flex items-center gap-4 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer">
                                <div className="text-black-900 flex items-center justify-center">
                                    <Settings width={20} height={20} />
                                </div>
                                <span>{t(profileMenu.accountSettings)}</span>
                            </div>
                        </ActiveLink>
                    </li>

                    <li className="list-none">
                        <Separator className="my-2" />
                    </li>
                    <li
                        onClick={handleLogout}
                        className="flex items-center gap-4 px-[20px] py-[10px] h-[36px] body4 !text-red-500 hover:bg-red-100 cursor-pointer"
                    >
                        <div className="flex items-center justify-center">
                            <LogOut width={20} height={20} />
                        </div>
                        <span>{t(profileMenu.logout)}</span>
                    </li>
                </ul>
            </PopoverContent>
        </Popover>
    );
}
