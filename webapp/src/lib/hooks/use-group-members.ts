import { useTranslation } from 'react-i18next';

import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAddResponderOnGroupMutation, useDeleteResponderFromGroupMutation } from '@app/store/workspaces/api';


interface IGroupMembersprops {
    emails?: Array<string>;
    email?: string;
    group: ResponderGroupDto;
    workspaceId: string;
}

export function useGroupMember() {
    const { toast } = useToast();
    const [addMember, addMemberResponse] = useAddResponderOnGroupMutation();
    const [removeMember, removeMemberResponse] = useDeleteResponderFromGroupMutation();
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const removeMemberFromGroup = async ({ email, group, workspaceId }: IGroupMembersprops) => {
        try {
            await removeMember({
                workspaceId: workspaceId,
                groupId: group.id,
                emails: [email]
            });

            toast({ description: t(toastMessage.removeFromGroup).toString() });
            closeModal();
        } catch (error) {
            toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
    };

    const addMembersOnGroup = async ({ emails, email, group, workspaceId }: IGroupMembersprops) => {
        try {
            if (emails && group.emails?.some((groupEmail) => emails?.includes(groupEmail))) {
                toast({ description: t(toastMessage.alreadyInGroup).toString(), variant: 'destructive' });
                return;
            }
            await addMember({
                workspaceId: workspaceId,
                groupId: group.id,
                emails: emails ?? [email]
            });
            toast({ description: t(toastMessage.addedOnGroup).toString() });
            closeModal();
        } catch (error) {
            toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
    };
    return {
        removeMemberFromGroup,
        addMembersOnGroup,
        addMemberResponse,
        removeMemberResponse
    };
}