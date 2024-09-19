import React from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import Delete from '@Components/Common/Icons/Common/Delete';
import { MoreHoriz } from '@mui/icons-material';
import { IconButton, ListItemIcon, Menu, MenuItem } from '@mui/material';

import { useModal } from '@app/Components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { WorkspaceInvitationDto, WorkspaceMembersDto } from '@app/models/dtos/WorkspaceMembersDto';


interface IMemberOptionProps {
    member?: WorkspaceMembersDto;
    invitation?: WorkspaceInvitationDto;
}

export default function MemberOptions({ member, invitation }: IMemberOptionProps) {
    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const [currentActiveMember, setCurrentActiveMember] = React.useState<any | null>(null);
    const open = Boolean(anchorEl);
    const { t } = useTranslation();
    const { openModal } = useModal();
    const handleClick = (event: React.MouseEvent<HTMLElement>, f: any) => {
        event.preventDefault();
        event.stopPropagation();
        setAnchorEl(event.currentTarget);
        setCurrentActiveMember(f);
    };

    return (
        <>
            <Tooltip title={t(toolTipConstant.Options)}>
                <IconButton
                    className="rounded-[4px] text-black-900 hover:rounded-[4px] hover:bg-black-200"
                    onClick={(e) => handleClick(e, member)}
                    size="small"
                    aria-controls={open ? 'forms-menu' : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <MoreHoriz />
                </IconButton>
            </Tooltip>
