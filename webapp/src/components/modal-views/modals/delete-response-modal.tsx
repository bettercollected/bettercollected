import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
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

    return <GenericHalfModal headerTitle="Delete response" title="Are you sure to delete this response?" type={'danger'} positiveAction={handleDelete} />;
}