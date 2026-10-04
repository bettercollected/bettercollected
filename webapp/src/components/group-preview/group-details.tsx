import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';

import GroupInfo from '@app/components/group/group-info';
import { buttonConstant } from '@app/constants/locales/button';
import { toastMessage } from '@app/constants/locales/toast-message';
import { GroupInfoDto, ResponderGroupDto } from '@app/models/dtos/groups';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
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

    const { can } = useWorkspacePermissions();

    const canManageGroups = can(WorkspacePermission.MEMBERS_MANAGE);
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
            {canManageGroups && (
                <div className="flex justify-start mt-10">
                    <Button variant="secondary" size="medium" isLoading={updateGroupResponse.isLoading}>
                        {t(buttonConstant.saveChanges)}
                    </Button>
                </div>
            )}
        </form>
    );
}
