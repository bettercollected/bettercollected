import { useTranslation } from 'next-i18next';

import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';
import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';
import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
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
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const [trigger] = useDeleteWorkspaceMemberMutation();

    const handleDelete = () => {
        const response: any = trigger({ workspaceId: workspace.id, userId: member.id });
        if (response.data) {
            toast(t(toastMessage.memberRemovedFromWorkspace).toString(), { type: 'success' });
        }
        if (response.error) {
            toast(t(toastMessage.failedToRemoveUser).toString(), { type: 'error' });
        }
        closeModal();
    };

    return <GenericHalfModal type="danger" headerTitle="Delete Member" title={`Are you sure to delete ${getFullNameFromUser(member)}?`} subTitle={t(localesCommon.removeWarningMessage)} positiveAction={handleDelete} />;
}
