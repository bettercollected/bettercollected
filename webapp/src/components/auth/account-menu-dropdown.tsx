import React from 'react';

import _ from 'lodash';

import Logout from '@Components/Common/Icons/Logout';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { CreditScore } from '@mui/icons-material';
import { Divider, ListItem, ListItemIcon, ListItemText, MenuItem } from '@mui/material';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import WorkspaceAdminHoc from '@app/components/hoc/workspace-admin-hoc';
import { DashboardIcon } from '@app/components/icons/dashboard-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IAuthAccountMenuDropdownProps {
    fullWidth?: boolean;
    checkMyDataEnabled?: boolean;
}

AuthAccountMenuDropdown.defaultProps = {
    fullWidth: false,
    checkMyDataEnabled: false
};
export default function AuthAccountMenuDropdown({ fullWidth, checkMyDataEnabled }: IAuthAccountMenuDropdownProps) {
    const workspace = useAppSelector(selectWorkspace);

    const authStatus = useAppSelector(selectAuthStatus);
    const data: any = authStatus?.data ? authStatus.data : null;
    const isError = !!authStatus?.error;

    const screenSize = useBreakpoint();
    const { openModal } = useModal();

    const handleLogout = () => {
        openModal('LOGOUT_VIEW');
    };

    const handleCheckMyData = () => {
        openModal('LOGIN_VIEW', { isCustomDomain: true });
    };

    if (isError && checkMyDataEnabled)
        return (
            <Button size="small" variant="solid" onClick={handleCheckMyData}>
                Check My Data
            </Button>
        );
    if (!data || isError) return <div className="w-9 sm:w-32 h-9 rounded-[4px] animate-pulse bg-black-300" />;

    const user = data?.user;

    const profileName = _.capitalize(user?.first_name) + ' ' + _.capitalize(user?.last_name);

    return (
        <MenuDropdown
            id="account-menu"
            menuTitle="Account Settings"
            fullWidth={fullWidth}
            menuContent={
                <>
                    <AuthAccountProfileImage image={user?.profile_image} name={profileName} />
                    {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && (profileName?.trim() || user?.email || '')}
                </>
            }
            showExpandMore={['xs', '2xs', 'sm'].indexOf(screenSize) === -1}
        >
            <ListItem className="py-3 px-5 flex items-center hover:bg-brand-100" alignItems="flex-start">
                <ListItemIcon sx={{ margin: 0 }}>
                    <AuthAccountProfileImage size={40} image={user?.profile_image} name={profileName} />
                </ListItemIcon>
                <ListItemText
                    sx={{ margin: 0 }}
                    primaryTypographyProps={{ fontSize: '16px', lineHeight: '24px', color: '#212529' }}
                    primary={profileName ?? 'Signed in as'}
                    secondary={user?.email}
                    secondaryTypographyProps={{ fontSize: '12px', lineHeight: '20px', color: '#6C757D' }}
                />
            </ListItem>
            <Divider className="my-2" />
            <WorkspaceAdminHoc>
                <ActiveLink href={`${environments.ADMIN_DOMAIN.includes('localhost') ? 'http://' : 'https://'}${environments.ADMIN_DOMAIN}/${workspace.workspaceName}/dashboard`} referrerPolicy="no-referrer">
                    <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100">
                        <ListItemIcon>
                            <DashboardIcon width={20} height={20} />
                        </ListItemIcon>
                        <span>My Dashboard</span>
                    </MenuItem>
                </ActiveLink>
                {user.stripe_customer_id && (
                    <ActiveLink href={`${environments.API_ENDPOINT_HOST}/stripe/session/create/portal`} referrerPolicy="no-referrer">
                        <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100">
                            <ListItemIcon>
                                <CreditScore fontSize="small" />
                            </ListItemIcon>
                            <span>Billing</span>
                        </MenuItem>
                    </ActiveLink>
                )}
            </WorkspaceAdminHoc>

            <Divider className="my-2" />
            <MenuItem onClick={handleLogout} sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-red-100 !text-red-500">
                <ListItemIcon>
                    <Logout width={20} height={20} />
                </ListItemIcon>
                <span>Logout</span>
            </MenuItem>
        </MenuDropdown>
    );
}
