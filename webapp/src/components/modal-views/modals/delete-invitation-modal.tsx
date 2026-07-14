import { useTranslation } from 'react-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { WorkspaceInvitationDto } from '@app/models/dtos/workspace-member-dto';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';


interface IDeleteInvitationModalProps {
    invitation: WorkspaceInvitationDto;
}

export default function DeleteInvitationModal({ invitation }: IDeleteInvitationModalProps) {
    const { toast } = useToast();
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const [trigger] = useDeleteWorkspaceInvitationMutation();

    const handleDelete = async () => {
        const response: any = await trigger({ workspaceId: workspace.id, invitationToken: invitation.invitationToken });
        if (response.data) {
            toast({ description: t(toastMessage.invitationDeleted).toString() });
        }
        if (response.error) {
            toast({ description: t(toastMessage.failedInvitationDeletion).toString(), variant: 'destructive' });
        }
        closeModal();
    };

    return <GenericHalfModal type="danger" headerTitle="Delete Invitation" title={`Are you sure to delete invitation of ${invitation.email}?`} positiveAction={handleDelete} />;
}