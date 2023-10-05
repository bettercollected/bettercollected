import React from 'react';

import EditIcon from '@Components/Common/Icons/Edit';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import ShareIcon from '@Components/Common/Icons/ShareIcon';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem } from '@mui/material';

import { EyeIcon } from '@app/components/icons/eye-icon';

interface IWorkspaceOptionsProps {
    onClickEdit: () => void;
    onOpenLink: () => void;
    onShareWorkspace: () => void;
    isAdmin?: boolean;
}

export default function WorkspaceOptions({ isAdmin, onClickEdit, onOpenLink, onShareWorkspace }: IWorkspaceOptionsProps) {
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
            <MenuItem onClick={onOpenLink}>
                <ListItemIcon>
                    <EyeIcon height={20} width={20} />
                </ListItemIcon>
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
