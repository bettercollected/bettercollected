'use client';

import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import _ from 'lodash';
import Divider from '@Components/Common/DataDisplay/Divider';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import Billing from '@Components/Common/Icons/Dashboard/Billing';
import DashboardIcon from '@Components/Common/Icons/Dashboard/Dashboard';
import Logout from '@Components/Common/Icons/Dashboard/Logout';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import WorkspaceAdminSelector from '@Components/HOCs/WorkspaceAdminSelector';
import { ListItem, ListItemIcon, ListItemText, MenuItem } from '@mui/material';
import AuthAccountProfileImage from '@app/Components/auth/account-profile-image';
import { useModal } from '@app/Components/modal-views/context';
import ActiveLink from '@app/Components/ui/links/active-link';
import environments from '@app/configs/environments';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useGetStatusQuery } from '@app/store/auth/api';
import { setAuth } from '@app/store/auth/slice';

interface IAuthAccountMenuDropdownProps {
    isClientDomain?: boolean;
    fullWidth?: boolean;
    hideMenu?: boolean;
    className?: string;
    menuContent?: React.ReactNode | React.ReactNode[];
    showExpandMore?: boolean;
}

export default function AuthAccountMenuDropdownApp({
    isClientDomain = false,
    fullWidth = false,
    hideMenu = false,
    className = '',
    showExpandMore,
    menuContent
}: IAuthAccountMenuDropdownProps) {
    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    const dispatch = useAppDispatch();

    const { data } = useGetStatusQuery()
    const user = data ?? null;

    const screenSize = useBreakpoint();
    const { openModal } = useModal();

    useEffect(() => {
        if (user && user?.id) {
            dispatch(setAuth({ ...user, isAdmin: workspace?.ownerId == user.id }));
        }
    }, [user?.id]);

    const handleLogout = () => {
        openModal('LOGOUT_VIEW', { workspace, isClientDomain: isClientDomain });
    };

    if (user?.isLoading) return <div className="bg-black-300 h-9 w-9 animate-pulse rounded-[4px] sm:w-32" />;
    if ((!user?.isLoading && !user?.id) || hideMenu) return null;

    const profileName = user?.firstName || user?.lastName ? _.capitalize(user?.firstName) + ' ' + _.capitalize(user?.lastName) : null;

    const newMenuContent = menuContent ?? (
        <>
            <AuthAccountProfileImage size={['xs', '2xs'].indexOf(screenSize) === -1 ? 36 : 28} image={user?.profileImage} name={user?.firstName || user?.lastName || user.email} />
            {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && (profileName?.trim() || user?.email || '')}
        </>
    );

    return (
        <MenuDropdown className={className} id="account-menu" menuTitle={t(profileMenu.accountSettings)} fullWidth={fullWidth} menuContent={newMenuContent} showExpandMore={showExpandMore ?? ['xs', '2xs', 'sm'].indexOf(screenSize) === -1}>
            <ListItem className="hover:bg-brand-100 flex items-center px-5 py-3" alignItems="flex-start">
                <ListItemIcon sx={{ margin: 0 }}>
                    <AuthAccountProfileImage size={40} image={user?.profileImage} name={profileName ?? ''} />
                </ListItemIcon>
                <ListItemText
                    sx={{ margin: 0 }}
                    primaryTypographyProps={{ fontSize: '16px', lineHeight: '24px', color: '#212529' }}
                    primary={profileName ?? 'Signed in as'}
                    secondary={user?.email}
                    secondaryTypographyProps={{ fontSize: '12px', lineHeight: '20px', color: '#6C757D' }}
                />
            </ListItem>
            <WorkspaceAdminSelector>
                <Divider className="my-2" />
                {isClientDomain && (
                    <ActiveLink href={`${environments.ADMIN_DOMAIN.includes('localhost') ? 'http://' : 'https://'}${environments.ADMIN_DOMAIN}/${workspace.workspaceName}/dashboard`} referrerPolicy="no-referrer">
                        <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100">
                            <ListItemIcon className="text-black-900">
                                <DashboardIcon width={20} height={20} />
                            </ListItemIcon>
                            <span>{t(profileMenu.myDashboard)}</span>
                        </MenuItem>
                    </ActiveLink>
                )}
                {user.stripeCustomerId && (
                    <ActiveLink href={`${environments.API_ENDPOINT_HOST}/stripe/session/create/portal`} referrerPolicy="no-referrer">
                        <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100">
                            <ListItemIcon className="text-black-900">
                                <Billing width={20} height={20} />
                            </ListItemIcon>
                            <span>{t(profileMenu.billing)}</span>
                        </MenuItem>
                    </ActiveLink>
                )}
                <ActiveLink href={`/${workspace.workspaceName}/dashboard/account-settings`}>
                    <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100">
                        <ListItemIcon className="text-black-900">
                            <SettingsIcon width={22} height={22} className="stroke-black-800" />
                        </ListItemIcon>
                        <span>{t(profileMenu.accountSettings)}</span>
                    </MenuItem>
                </ActiveLink>
            </WorkspaceAdminSelector>
            <Divider className="my-2" />
            <MenuItem onClick={handleLogout} sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100">
                <ListItemIcon className="text-black-900">
                    <Logout width={20} height={20} />
                </ListItemIcon>
                <span>{t(profileMenu.logout)}</span>
            </MenuItem>
        </MenuDropdown>
    );
}
