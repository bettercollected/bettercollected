import React from 'react';

import { useTranslation } from 'next-i18next';

import DeleteIcon from '@Components/Common/Icons/Delete';
import { Typography } from '@mui/material';
import { toast } from 'react-toastify';

import { Plus } from '@app/components/icons/plus';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useGroupMember } from '@app/lib/hooks/use-group-members';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useDeleteResponderFromGroupMutation } from '@app/store/workspaces/api';

import { useModal } from '../modal-views/context';

export default function GroupMembers({ group, workspace }: { group: ResponderGroupDto; workspace: WorkspaceDto }) {
    const { t } = useTranslation();
    const { removeMemberFromGroup } = useGroupMember();
    const { openModal } = useModal();
    return (
        <div>
            <div className="flex  justify-between">
                <p className="body1">
                    {t(members.default)} ({group.emails.length})
                </p>
                <div onClick={() => openModal('ADD_MEMBER', { group })} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6"> Add Member</Typography>
                </div>
            </div>
            <p className="body4 leading-none mt-5 mb-10 md:max-w-[355px] !text-black-700 break-all">{t(groupConstant.description)}</p>
            <div className="flex flex-col gap-2">
                {group.emails.map((email) => {
                    return (
                        <div key={email} className="flex md:max-w-[610px] justify-between body4 bg-white px-4  rounded py-5 !text-black-800">
                            <span>{email}</span>
                            <DeleteIcon onClick={() => removeMemberFromGroup({ email, group, workspaceId: workspace.id })} className="h-7 w-7 p-1 cursor-pointer rounded hover:bg-black-200 text-red-500" />
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
