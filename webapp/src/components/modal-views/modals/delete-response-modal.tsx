import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { useDeleteResponseMutation } from '@app/store/workspaces/api';
import ModalButton from "@Components/Common/Input/Button/ModalButton";
import {ButtonSize, ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";

export default function DeleteResponseModal({ workspace, formId, responseId, navigateToForm = false }: any) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const router = useRouter();

    const [deleteResponse] = useDeleteResponseMutation();

    const handleDelete = async () => {
        const response: any = await deleteResponse({ workspaceId: workspace.id, formId, responseId });
        if (response?.data) {
            toast('Response Deleted', { type: 'success' });
            if (navigateToForm) router.push(`/${workspace.workspaceName}/dashboard/forms/${formId}`);
            closeModal();
        } else {
            toast('Error Deleting Response', { type: 'error' });
        }
    };
    return (
        <div className="bg-white rounded relative p-10">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="sh3 mb-5">Are you sure to delete this response?</div>
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
