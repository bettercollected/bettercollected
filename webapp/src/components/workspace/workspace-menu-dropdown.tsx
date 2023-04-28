import React from 'react';

import { useRouter } from 'next/router';

import _ from 'lodash';

import { ExpandMore } from '@mui/icons-material';
import { Divider, IconButton, ListItem, Menu, Tooltip } from '@mui/material';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { Check } from '@app/components/icons/check';
import { Plus } from '@app/components/icons/plus';
import Loader from '@app/components/ui/loader';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IWorkspaceMenuDropdownProps {
    fullWidth?: boolean;
}

WorkspaceMenuDropdown.defaultProps = {
    fullWidth: false
};
export default function WorkspaceMenuDropdown({ fullWidth }: IWorkspaceMenuDropdownProps) {
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

    const open = Boolean(anchorEl);

    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetAllMineWorkspacesQuery();
    const router = useRouter();

    const screenSize = useBreakpoint();

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleChangeWorkspace = (space: WorkspaceDto) => {
        router.push(`/${space.workspaceName}/dashboard`);
    };

    const handleCreateWorkspace = () => {
        // TODO: Create workspace here
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const fullWorkspaceName = workspace?.title || workspace?.workspaceName || '';
    const workspaceName = toEndDottedStr(fullWorkspaceName, 15);

    return (
        <>
            <Tooltip title={fullWorkspaceName} arrow enterDelay={400} enterTouchDelay={0}>
                <IconButton
                    className={`hover:rounded-[4px] hover:bg-black-200 rounded-[4px] ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`}
                    onClick={handleClick}
                    size="small"
                    aria-controls={open ? 'account-menu' : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <span className="flex items-center gap-3">
                        <AuthAccountProfileImage image={workspace?.profileImage} name={workspaceName} />
                        {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && <p className="body1">{workspaceName}</p>}
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
                        width: 289,
                        overflow: 'hidden',
                        borderRadius: 2,
                        filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
                        mt: 1.5,
                        '& .MuiAvatar-root': {
                            width: 40,
                            height: 40,
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
                {isLoading ? (
                    <ListItem disablePadding className="px-5 py-3 flex justify-center items-center" alignItems="center">
                        <Loader />
                    </ListItem>
                ) : !!data && Array.isArray(data) ? (
                    data.map((space: WorkspaceDto) => (
                        <ListItem key={space.id} disablePadding className="px-5 py-3" alignItems="flex-start">
                            <IconButton className={`hover:rounded-[4px] hover:bg-black-200 rounded-[4px] ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`} onClick={() => handleChangeWorkspace(space)} size="small">
                                <div className="flex justify-between w-full items-center gap-4">
                                    <div className="flex items-center gap-3">
                                        <AuthAccountProfileImage size={40} image={space?.profileImage} name={space?.title} />
                                        {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && (
                                            <Tooltip title={space?.title}>
                                                <p className="body3 !not-italic">{space?.title}</p>
                                            </Tooltip>
                                        )}
                                    </div>
                                    {workspace.id === space.id && <Check color="#0764EB" />}
                                </div>
                            </IconButton>
                        </ListItem>
                    ))
                ) : (
                    <ListItem disablePadding className="px-5 py-3" alignItems="center">
                        <IconButton className={`hover:rounded-[4px] hover:bg-black-200 rounded-[4px] ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`} onClick={handleClick} size="small">
                            <div className="flex justify-between w-full items-center gap-4">
                                <div className="flex items-center gap-3">
                                    <AuthAccountProfileImage size={40} image={workspace?.profileImage} name={workspaceName} />
                                    {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && (
                                        <Tooltip title={fullWorkspaceName}>
                                            <p className="body3 !not-italic">{workspaceName}</p>
                                        </Tooltip>
                                    )}
                                </div>
                                <Check color="#0764EB" />
                            </div>
                        </IconButton>
                    </ListItem>
                )}
                {!isLoading && (
                    <div>
                        <Divider className="my-2" />
                        <ListItem disablePadding className="px-5 py-3" alignItems="center">
                            <IconButton className={`hover:rounded-[4px] hover:bg-black-200 rounded-[4px] ${fullWidth ? 'w-full flex justify-between' : 'w-fit'}`} onClick={handleCreateWorkspace} size="small">
                                <span className="flex justify-between w-full items-center gap-4">
                                    <div className="flex items-center gap-3">
                                        <Plus className="text-black-500" />
                                        {['xs', '2xs', 'sm'].indexOf(screenSize) === -1 && <p className="body3 !not-italic !text-black-500">Create a new workspace</p>}
                                    </div>
                                </span>
                            </IconButton>
                        </ListItem>
                    </div>
                )}
            </Menu>
        </>
    );
}
