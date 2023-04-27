import React from 'react';

import _ from 'lodash';

import { CreditScore, ExpandMore, Logout } from '@mui/icons-material';
import { Divider, IconButton, ListItem, ListItemIcon, ListItemText, Menu, MenuItem, Tooltip, Typography } from '@mui/material';

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
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

    const open = Boolean(anchorEl);
    const workspace = useAppSelector(selectWorkspace);

    const authStatus = useAppSelector(selectAuthStatus);
    const data: any = authStatus?.data ? authStatus.data : null;
    const isError = !!authStatus?.error;

    const screenSize = useBreakpoint();
    const { openModal } = useModal();

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleLogout = () => {
        openModal('LOGOUT_VIEW');
        handleClose();
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
        <>
            <Tooltip title="Account Settings" arrow enterDelay={400} enterTouchDelay={0}>
                <IconButton
                    className={`hover:rounded-[4px] hover:bg-black-200 rounded-[4px] ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`}
                    onClick={handleClick}
                    size="small"
                    aria-controls={open ? 'account-menu' : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <span className="flex items-center">
                        <AuthAccountProfileImage image={user?.profile_image} name={profileName} />
                        {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && <p className="body4 ml-2 mr-[14px]">{profileName?.trim() || user?.email || ''}</p>}
                    </span>
                    <ExpandMore className={`${open ? 'rotate-180' : '-rotate-0'} h-7 w-7 text-black-900 transition-all duration-300`} />
                </IconButton>
            </Tooltip>
            <Menu
                anchorEl={anchorEl}
                id="account-menu"
                open={open}
                onClose={handleClose}
                onClick={handleClose}
                draggable
                disableScrollLock={true}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        width: 320,
                        overflow: 'hidden',
                        borderRadius: 1,
                        filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
                        mt: 1.5,
                        '& .MuiAvatar-root': {
                            width: 32,
                            height: 32,
                            ml: -0.5,
                            mr: 2,
                            borderRadius: 1
                        },
                        '&:before': {
                            content: '""',
                            display: 'block',
                            position: 'absolute',
                            top: 0,
                            right: 14,
                            width: 10,
                            height: 10,
                            bgcolor: 'background.paper',
                            transform: 'translateY(-50%) rotate(45deg)',
                            zIndex: 0
                        }
                    }
                }}
                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
                <ListItem className="py-2 px-4" alignItems="flex-start">
                    <ListItemIcon className="!min-w-[39px]">
                        <AuthAccountProfileImage image={user?.profile_image} name={profileName} />
                    </ListItemIcon>
                    <ListItemText
                        primary="Signed in as"
                        secondary={
                            <React.Fragment>
                                <Typography sx={{ display: 'inline', fontStyle: 'italic' }} component="span" variant="body2" color="text.secondary">
                                    {user?.email}
                                </Typography>
                            </React.Fragment>
                        }
                    />
                </ListItem>
                <Divider className="mb-2" />
                <WorkspaceAdminHoc>
                    <ActiveLink href={`${environments.ADMIN_DOMAIN.includes('localhost') ? 'http://' : 'https://'}${environments.ADMIN_DOMAIN}/${workspace.workspaceName}/dashboard`} referrerPolicy="no-referrer">
                        <MenuItem>
                            <ListItemIcon>
                                <DashboardIcon width={20} height={20} />
                            </ListItemIcon>
                            <span>My Dashboard</span>
                        </MenuItem>
                    </ActiveLink>
                    {user.stripe_customer_id && (
                        <ActiveLink href={`${environments.API_ENDPOINT_HOST}/stripe/session/create/portal`} referrerPolicy="no-referrer">
                            <MenuItem>
                                <ListItemIcon>
                                    <CreditScore fontSize="small" />
                                </ListItemIcon>
                                <span>Billing</span>
                            </MenuItem>
                        </ActiveLink>
                    )}
                </WorkspaceAdminHoc>

                <MenuItem onClick={handleLogout}>
                    <ListItemIcon>
                        <Logout fontSize="small" color="error" />
                    </ListItemIcon>
                    <span className="text-[#d32f2f]">Logout</span>
                </MenuItem>
            </Menu>
        </>
    );
}
