import React from 'react';

import { useTranslation } from 'next-i18next';

import EllipsisOption from '@Components/Common/Icons/Common/EllipsisOption';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import ShareIcon from '@Components/Common/Icons/Common/ShareIcon';
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
    const { t } = useTranslation();
    return (
        <MenuDropdown id="workspace-dropdown" showExpandMore={false} menuTitle="" menuContent={<EllipsisOption />}>
            {isAdmin && (
                <MenuItem onClick={onClickEdit}>
                    <ListItemIcon>
                        <SettingsIcon strokeWidth={1} width={20} height={20} />
                    </ListItemIcon>
                    <span> {t('SETTINGS')}</span>
                </MenuItem>
            )}
            <MenuItem>
                <ActiveLink href={workspaceUrl} target="_blank" referrerPolicy="no-referrer">
                    <ListItemIcon>
                        <EyeIcon height={20} width={20} />
                    </ListItemIcon>
                </ActiveLink>
                <span> {t('BUTTON.OPEN_WORKSPACE')}</span>
            </MenuItem>
            <MenuItem onClick={onShareWorkspace}>
                <ListItemIcon>
                    <ShareIcon strokeWidth={1} height={20} width={20} />
                </ListItemIcon>
                <span> {t('SHARE_WORKSPACE')}</span>
            </MenuItem>
        </MenuDropdown>
    );
}
