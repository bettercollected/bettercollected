import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
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

    return (
        <div className="rounded p-10 bg-white items-center w-full max-w-[465px] flex flex-col relative">
            <Close
                className="absolute top-5 right-5"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="sh3 mb-5">
                {t(localesCommon.remove)} {getFullNameFromUser(member)}?
            </div>
            <div className="body4 text-black-600 text-center mb-10">{t(localesCommon.removeWarningMessage)}</div>
            <div className="flex w-full gap-4 justify-between">
                <Button data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleDelete}>
                    {t(buttonConstant.delete)}
                </Button>
                <Button variant="solid" color="gray" size="medium" className="!bg-black-500" onClick={() => closeModal()}>
                    {t(buttonConstant.cancel)}
                </Button>
            </div>
        </div>
    );
}
