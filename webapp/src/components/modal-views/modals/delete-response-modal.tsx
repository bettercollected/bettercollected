import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { useDeleteResponseMutation } from '@app/store/workspaces/api';

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
