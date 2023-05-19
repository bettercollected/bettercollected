import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { buttons } from '@app/constants/locales/buttons';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function DeleteInvitationModal({ invitation }: any) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const [trigger] = useDeleteWorkspaceInvitationMutation();

    const handleDelete = async () => {
        const response: any = await trigger({ workspaceId: workspace.id, invitationToken: invitation.invitation_token });
        if (response.data) {
            toast(t(toastMessage.invitationDeleted).toString(), { type: 'success' });
        }
        if (response.error) {
            toast(t(toastMessage.failedInvitationDeletion).toString(), { type: 'error' });
        }
        closeModal();
    };

    return (
        <div className="rounded p-10 bg-white items-center w-full max-w-[465px] flex flex-col relative">
            <Close
                className="absolute cursor-pointer top-5 right-5"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="sh3 mb-5">
                {t(localesGlobal.removeInvitationFor)} {invitation.email}?
            </div>
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
