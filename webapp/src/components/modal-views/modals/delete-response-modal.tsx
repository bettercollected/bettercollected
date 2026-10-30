import { useState } from 'react';

import { useRouter } from 'next/navigation';

import GenericHalfModal from '@Components/common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { useDeleteResponseMutation } from '@app/store/workspaces/api';

export default function DeleteResponseModal({ workspace, formId, responseId, navigateTo }: any) {
    const { toast } = useToast();
    const { closeModal } = useModal();
    const router = useRouter();
    const [isDeleting, setIsDeleting] = useState(false);

    const [deleteResponse] = useDeleteResponseMutation();

    const handleDelete = async () => {
        setIsDeleting(true);
        const response: any = await deleteResponse({ workspaceId: workspace.id, formId, responseId });
        setIsDeleting(false);
        if (response?.data) {
            toast({ description: 'Response deleted' });
            // from a response's own page, back to the list (a relative path of ours, never one from the URL)
            if (typeof navigateTo === 'string' && navigateTo.startsWith('/') && !navigateTo.startsWith('//')) router.push(navigateTo);
            closeModal();
        } else {
            toast({ description: 'Could not delete the response. Try again.', variant: 'destructive' });
        }
    };

    return (
        <GenericHalfModal
            headerTitle="Delete response"
            title="Delete this response permanently?"
            subTitle="The response and any uploaded files are removed and can't be recovered. If the responder asked for this deletion, their request is marked as completed."
            type="danger"
            positiveText="Delete response"
            loading={isDeleting}
            positiveAction={handleDelete}
        />
    );
}
