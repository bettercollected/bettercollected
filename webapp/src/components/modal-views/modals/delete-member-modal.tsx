import { useTranslation } from 'next-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { localesCommon } from '@app/constants/locales/common';
import { toastMessage } from '@app/constants/locales/toast-message';
import { WorkspaceMembersDto } from '@app/models/dtos/WorkspaceMembersDto';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceMemberMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';


interface IDeleteMemberModalProps {
    member: WorkspaceMembersDto;
}

export default function DeleteMemberModal({ member }: IDeleteMemberModalProps) {
    const { toast } = useToast();
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const [trigger] = useDeleteWorkspaceMemberMutation();

    const handleDelete = () => {
        const response: any = trigger({ workspaceId: workspace.id, userId: member.id });
        if (response.data) {
            toast({ description: t(toastMessage.memberRemovedFromWorkspace).toString() });
        }
        if (response.error) {
            toast({ description: t(toastMessage.failedToRemoveUser).toString(), variant: 'destructive' });
        }
        closeModal();
    };

    return <GenericHalfModal type="danger" headerTitle="Delete Member" title={`Are you sure to delete ${getFullNameFromUser(member)}?`} subTitle={t(localesCommon.removeWarningMessage)} positiveAction={handleDelete} />;
}