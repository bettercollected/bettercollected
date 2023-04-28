import React from 'react';

import Image from 'next/image';

import _ from 'lodash';

import { Domain, Logout, ManageAccounts, PrivacyTip } from '@mui/icons-material';
import { Avatar, Box, Divider, IconButton, Menu, MenuItem, Tooltip } from '@mui/material';

import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

import { HomeIcon } from '../icons/home';
import { useModal } from '../modal-views/context';
import Hamburger from '../ui/hamburger';

interface IWorkspaceLoginMenuItems {
    authStatus: any;
    handleLogout: any;
    workspace: WorkspaceDto;
    isFormCreator: boolean;
}

export default function WorkspaceLoginMenuItems({ authStatus, handleLogout, workspace, isFormCreator }: IWorkspaceLoginMenuItems) {
    const { openModal } = useModal();

    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);
    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };
    const handleClose = () => {
        setAnchorEl(null);
    };

    const user = authStatus?.data?.user;

    const profileName = _.capitalize(user?.first_name) + ' ' + _.capitalize(user?.last_name);

    const handleUpdateTocAndPrivacyPolicy = () => {
        openModal('UPDATE_TERMS_OF_SERVICE_AND_PRIVACY_POLICY');
    };

    return (
        <>
            <Box sx={{ display: 'flex', alignItems: 'center', textAlign: 'center' }}>
                <Tooltip title="Account settings" arrow placement="bottom-end" enterDelay={300} enterTouchDelay={0}>
                    <div onClick={handleClick} aria-controls={open ? 'account-menu' : undefined} aria-haspopup="true" aria-expanded={open ? 'true' : undefined}>
                        <Hamburger />
                    </div>
                </Tooltip>
            </Box>
            <Menu
                anchorEl={anchorEl}
                id="account-menu"
                open={open}
                onClose={handleClose}
                onClick={handleClose}
                disableScrollLock
                PaperProps={{
                    elevation: 0,
                    sx: {
                        overflow: 'visible',
                        filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
                        mt: 1.5,
                        '& .MuiAvatar-root': {
                            width: 32,
                            height: 32,
                            ml: -0.5,
                            mr: 1
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
                <MenuItem onClick={handleClose}>
                    {user?.profile_image ? <Image src={user?.profile_image} alt={isFormCreator ? 'C' : 'R'} className="rounded-full" width={48} height={48} /> : <Avatar>{isFormCreator ? 'C' : 'R'}</Avatar>}
                    <div className=" ml-4 flex flex-col">
                        <span className="text-gray-800 font-bold">{profileName.trim() || user?.email || ''}</span>
                        <span className="text-gray-600 italic">{isFormCreator ? 'Form Creator' : 'Form Responder'}</span>
                    </div>
                </MenuItem>
                <Divider />
                {isFormCreator && (
                    <>
                        <a
                            className="w-full"
                            target="_blank"
                            referrerPolicy="no-referrer"
                            href={`${environments.ADMIN_DOMAIN.includes('localhost') ? 'http://' : 'https://'}${environments.ADMIN_DOMAIN}/${workspace.workspaceName}/dashboard`}
                            rel="noreferrer"
                        >
                            <MenuItem className="hover:bg-blue-500 hover:text-white text-gray-900 group flex w-full items-center">
                                <div className="flex space-x-4">
                                    <HomeIcon width={20} height={20} />
                                    <span>My Dashboard</span>
                                </div>
                            </MenuItem>
                        </a>
                        <MenuItem onClick={handleUpdateTocAndPrivacyPolicy} className="hover:bg-blue-500 hover:text-white text-gray-900 group flex w-full items-center">
                            <div className="flex space-x-4">
                                <PrivacyTip width={20} height={20} />
                                <span className="!ml-3">Terms of service and Privacy Policy</span>
                            </div>
                        </MenuItem>
                        <Divider />
                        <p className="text-red-900 ml-[14px]">Danger Zone</p>
                        <MenuItem onClick={() => openModal('UPDATE_WORKSPACE_HANDLE')} className="hover:bg-red-900 hover:text-white text-red-900 group flex w-full items-center">
                            <div className="flex space-x-4">
                                <ManageAccounts width={20} height={20} />
                                <span className="!ml-3">Update Workspace Handle</span>
                            </div>
                        </MenuItem>
                        <MenuItem onClick={() => openModal('UPDATE_WORKSPACE_DOMAIN')} className="hover:bg-red-900 hover:text-white text-red-900 group flex w-full items-center">
                            <div className="flex space-x-4">
                                <Domain width={20} height={20} />
                                <span className="!ml-3">Update Custom Domain</span>
                            </div>
                        </MenuItem>
                        <Divider />
                    </>
                )}
                <MenuItem className="hover:bg-red-500 hover:text-white text-red-500 group flex w-full items-center space-x-4" onClick={handleLogout}>
                    <Logout height={20} width={20} className="!rounded-xl" />
                    <span className="!ml-3">Sign off</span>
                </MenuItem>
            </Menu>
        </>
    );
}
