import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { buttons } from '@app/constants/locales/buttons';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceMemberMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';

export default function DeleteMemberModal({ member }: any) {
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
                {t(localesGlobal.remove)} {getFullNameFromUser(member)}?
            </div>
            <div className="body4 text-black-600 text-center mb-10">{t(localesGlobal.removeWarningMessage)}</div>
            <div className="flex w-full gap-4 justify-end">
                <Button data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleDelete}>
                    {t(buttons.delete)}
                </Button>
                <Button variant="solid" color="gray" size="medium" className="!bg-black-500" onClick={() => closeModal()}>
                    {t(buttons.cancel)}
                </Button>
            </div>
        </div>
    );
}
