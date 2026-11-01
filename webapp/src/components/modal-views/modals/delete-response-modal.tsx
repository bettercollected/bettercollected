import { useState } from 'react';

import { useRouter } from 'next/navigation';

import { useTranslation } from 'react-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { useDeleteResponseMutation } from '@app/store/workspaces/api';
import { isSameSitePath } from '@app/utils/same-site-path';

interface DeleteResponseModalProps {
    workspace: { id: string };
    formId: string;
    responseId: string;
    /** From a response's own page: where to go after the delete (a path of ours, built by the page). */
    navigateTo?: string;
    /**
     * Told when the delete starts (true) and when it failed (false), so the
     * page showing the response stops asking for it: the delete invalidates
     * it, and a refetch would flash "not found" before the page is left.
     */
    onDeleting?: (deleting: boolean) => void;
}

export default function DeleteResponseModal({ workspace, formId, responseId, navigateTo, onDeleting }: DeleteResponseModalProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const { closeModal } = useModal();
    const router = useRouter();
    const [isDeleting, setIsDeleting] = useState(false);

    const [deleteResponse] = useDeleteResponseMutation();

    const handleDelete = async () => {
        setIsDeleting(true);
        onDeleting?.(true);
        const response: any = await deleteResponse({ workspaceId: workspace.id, formId, responseId });
        setIsDeleting(false);
        if (response?.data) {
            toast({ description: t('RESPONSE_PAGE.DELETED_TOAST') });
            // from a response's own page, back to the list; replace: the deleted response's page is gone from history
            if (isSameSitePath(navigateTo)) router.replace(navigateTo);
            closeModal();
        } else {
            onDeleting?.(false);
            toast({ description: t('RESPONSE_PAGE.DELETE_FAILED'), variant: 'destructive' });
        }
    };

    return (
        <GenericHalfModal
            headerTitle={t('RESPONSE_PAGE.DELETE_RESPONSE')}
            title={t('RESPONSE_PAGE.DELETE_TITLE')}
            subTitle={t('RESPONSE_PAGE.DELETE_BODY')}
            type="danger"
            positiveText={t('RESPONSE_PAGE.DELETE_RESPONSE')}
            loading={isDeleting}
            positiveAction={handleDelete}
        />
    );
}
