import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import GenericHalfModal from '@Components/Common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { useDeleteResponseMutation } from '@app/store/workspaces/api';


export default function DeleteResponseModal({ workspace, formId, responseId, navigateToForm = false }: any) {
    const { toast } = useToast();
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const router = useRouter();

    const [deleteResponse] = useDeleteResponseMutation();

    const handleDelete = async () => {
        const response: any = await deleteResponse({ workspaceId: workspace.id, formId, responseId });
        if (response?.data) {
            toast({ description: 'Response Deleted' });
            if (navigateToForm) router.push(`/${workspace.workspaceName}/dashboard/forms/${formId}`);
            closeModal();
        } else {
            toast({ description: 'Error Deleting Response', variant: 'destructive' });
        }
    };

    return <GenericHalfModal headerTitle="Delete response" title="Are you sure to delete this response?" type={'danger'} positiveAction={handleDelete} />;
}