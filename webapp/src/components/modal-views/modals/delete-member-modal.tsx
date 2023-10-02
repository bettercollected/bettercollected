import { useTranslation } from 'next-i18next';

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
import ModalButton from "@Components/Common/Input/Button/ModalButton";
import {ButtonSize, ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";

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
            <div className="flex w-full gap-2 justify-between">
                <ModalButton data-testid="logout-button" buttonType={"Modal"} size={ButtonSize.Medium} variant={ButtonVariant.Danger} onClick={handleDelete}>
                    {t(buttonConstant.delete)}
                </ModalButton>
                <ModalButton buttonType={"Modal"} size={ButtonSize.Medium} variant={ButtonVariant.Secondary} onClick={() => closeModal()}>
                    {t(buttonConstant.cancel)}
                </ModalButton>
            </div>
        </div>
    );
}
