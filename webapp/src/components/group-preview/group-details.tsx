import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Typography } from '@mui/material';
import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import Button from '@app/components/ui/button/button';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { GroupInfoDto, ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useUpdateResponderGroupMutation } from '@app/store/workspaces/api';

import GroupInfo from '../group/group-info';

export default function GroupDetailsTab({ group }: { group: ResponderGroupDto }) {
    const { t } = useTranslation();
    const [updateResponderGroup, updateGroupResponse] = useUpdateResponderGroupMutation();
    const [groupInfo, setGroupInfo] = useState<GroupInfoDto>({
        name: group.name,
        description: group.description,
        emails: group.emails
    });
    const isAdmin = useAppSelector(selectIsAdmin);
    const workspace = useAppSelector((state) => state.workspace);
    const handleInput = (event: any) => {
        setGroupInfo({
            ...groupInfo,
            [event.target.id]: event.target.value
        });
    };

    const handleUpdateGroup = async (e: any) => {
        e.preventDefault();
        try {
            await updateResponderGroup({
                groupInfo: groupInfo,
                workspaceId: workspace.id,
                groupId: group.id
            }).unwrap();
            toast(t(toastMessage.updated).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    return (
        <form onSubmit={handleUpdateGroup} className="md:max-w-[618px]">
            <GroupInfo handleInput={handleInput} groupInfo={groupInfo} />
            {isAdmin && (
                <div className="flex justify-end mt-10">
                    <Button isLoading={updateGroupResponse.isLoading}>{t(buttonConstant.saveChanges)}</Button>
                </div>
            )}
        </form>
    );
}
