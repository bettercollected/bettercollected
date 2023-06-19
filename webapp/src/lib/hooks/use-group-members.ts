import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAddResponderOnGroupMutation, useDeleteResponderFromGroupMutation } from '@app/store/workspaces/api';
import { isEmailInGroup } from '@app/utils/groupUtils';

interface IGroupMembersprops {
    email: string;
    group: ResponderGroupDto;
    workspaceId: string;
}
export function useGroupMember() {
    const [addMember, addMemberResponse] = useAddResponderOnGroupMutation();
    const [removeMember, removeMemberResponse] = useDeleteResponderFromGroupMutation();
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const removeMemberFromGroup = async ({ email, group, workspaceId }: IGroupMembersprops) => {
        try {
            if (group.emails.length === 1) {
                toast(t(toastMessage.lastPersonOfGroup).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
                return;
            }

            await removeMember({
                workspaceId: workspaceId,
                groupId: group.id,
                emails: [email]
            });

            toast(t(toastMessage.removeFromGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const addMemberOnGroup = async ({ email, group, workspaceId }: IGroupMembersprops) => {
        try {
            if (isEmailInGroup(group, email)) {
                toast(t(toastMessage.alreadyInGroup).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
                return;
            }
            await addMember({
                workspaceId: workspaceId,
                groupId: group.id,
                emails: [email]
            }).unwrap();
            toast(t(toastMessage.addedOnGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    return {
        removeMemberFromGroup,
        addMemberOnGroup,
        addMemberResponse,
        removeMemberResponse
    };
}
