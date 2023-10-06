import React from 'react';

import Link from 'next/link';

import EditIcon from '@Components/Common/Icons/Edit';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import ShareIcon from '@Components/Common/Icons/ShareIcon';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem } from '@mui/material';

import { EyeIcon } from '@app/components/icons/eye-icon';
import ActiveLink from '@app/components/ui/links/active-link';

interface IWorkspaceOptionsProps {
    onClickEdit: () => void;
    onShareWorkspace: () => void;
    isAdmin?: boolean;
    workspaceUrl: string;
}

export default function WorkspaceOptions({ isAdmin, onClickEdit, onShareWorkspace, workspaceUrl }: IWorkspaceOptionsProps) {
    return (
        <MenuDropdown id="workspace-dropdown" showExpandMore={false} menuTitle="" menuContent={<EllipsisOption />}>
            {isAdmin && (
                <MenuItem onClick={onClickEdit}>
                    <ListItemIcon>
                        <EditIcon width={20} height={20} />
                    </ListItemIcon>
                    <span>Edit</span>
                </MenuItem>
            )}
            <MenuItem>
                <ActiveLink href={workspaceUrl} target="_blank" referrerPolicy="no-referrer">
                    <ListItemIcon>
                        <EyeIcon height={20} width={20} />
                    </ListItemIcon>
                </ActiveLink>
                <span>Open Link</span>
            </MenuItem>
            <MenuItem onClick={onShareWorkspace}>
                <ListItemIcon>
                    <ShareIcon height={20} width={20} />
                </ListItemIcon>
                <span>Share Workspace</span>
            </MenuItem>
        </MenuDropdown>
    );
}
