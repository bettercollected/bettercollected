import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import DeleteIcon from '@Components/Common/Icons/Delete';
import SearchInput from '@Components/Common/Search/SearchInput';
import { Typography } from '@mui/material';
import { toast } from 'react-toastify';

import { Plus } from '@app/components/icons/plus';
import { buttonConstant } from '@app/constants/locales/button';
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
    const [emails, setEmails] = useState(group.emails);
    const handleSearch = (event: any) => {
        const query = event.target.value;
        var updatedList = [...group.emails];
        updatedList = updatedList.filter((item) => {
            return item.toLowerCase().indexOf(query.toLowerCase()) !== -1;
        });
        setEmails(updatedList);
    };
    return (
        <div>
            <div className="flex  justify-between">
                <p className="body1">
                    {t(members.default)} ({group.emails.length})
                </p>
                <div onClick={() => openModal('ADD_MEMBER', { group })} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6">{t(buttonConstant.addMember)}</Typography>
                </div>
            </div>
            <p className="body4 leading-none mt-5 mb-10 md:max-w-[355px] !text-black-700 break-all">{t(groupConstant.description)}</p>
            {group.emails.length > 0 && (
                <div className=" flex flex-col md:max-w-[610px] gap-6">
                    <div className="sm:w-[240px]">
                        <SearchInput handleSearch={handleSearch} />
                    </div>
                    <div className="flex flex-col gap-2">
                        {emails.map((email) => {
                            return (
                                <div key={email} className="flex  justify-between body4 bg-white px-4  rounded py-5 !text-black-800">
                                    <span>{email}</span>
                                    <DeleteIcon onClick={() => removeMemberFromGroup({ email, group, workspaceId: workspace.id })} className="h-7 w-7 p-1 cursor-pointer rounded hover:bg-black-200 text-red-500" />
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
