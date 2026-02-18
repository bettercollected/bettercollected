import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import GroupInfo from '@app/Components/group/group-info';
import { buttonConstant } from '@app/constants/locales/button';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { GroupInfoDto, ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useUpdateResponderGroupMutation } from '@app/store/workspaces/api';

export default function GroupDetailsTab({ group }: { group: ResponderGroupDto }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [updateResponderGroup, updateGroupResponse] = useUpdateResponderGroupMutation();
    const [groupInfo, setGroupInfo] = useState<GroupInfoDto>({
        name: group.name,
        description: group.description,
        regex: group.regex
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
            toast({ description: t(toastMessage.updated).toString() });
        } catch (error) {
            toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
    };
    return (
        <form onSubmit={handleUpdateGroup} className="md:max-w-[618px]">
            <GroupInfo handleInput={handleInput} groupInfo={groupInfo} />
            {isAdmin && (
                <div className="flex justify-start mt-10">
                    <AppButton variant={ButtonVariant.Secondary} size={ButtonSize.Medium} isLoading={updateGroupResponse.isLoading}>
                        {t(buttonConstant.saveChanges)}
                    </AppButton>
                </div>
            )}
        </form>
    );
}
