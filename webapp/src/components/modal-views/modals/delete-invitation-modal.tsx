import { useTranslation } from 'next-i18next';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { WorkspaceInvitationDto } from '@app/models/dtos/WorkspaceMembersDto';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';


interface IDeleteInvitationModalProps {
    invitation: WorkspaceInvitationDto;
}

export default function DeleteInvitationModal({ invitation }: IDeleteInvitationModalProps) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const [trigger] = useDeleteWorkspaceInvitationMutation();

    const handleDelete = async () => {
        const response: any = await trigger({ workspaceId: workspace.id, invitationToken: invitation.invitationToken });
        if (response.data) {
            toast(t(toastMessage.invitationDeleted).toString(), { type: 'success' });
        }
        if (response.error) {
            toast(t(toastMessage.failedInvitationDeletion).toString(), { type: 'error' });
        }
        closeModal();
    };

    return <GenericHalfModal type="danger" headerTitle="Delete Invitation" title={`Are you sure to delete invitation of ${invitation.email}?`} positiveAction={handleDelete} />;
}