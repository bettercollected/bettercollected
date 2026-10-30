import { useState } from 'react';

import { useRouter } from 'next/navigation';

import GenericHalfModal from '@Components/common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { useDeleteResponseMutation } from '@app/store/workspaces/api';

/**
 * Whether `navigateTo` is a path of this site: a relative path, no "//" or
 * "\" (browsers read "/\evil.example" as another host), and resolving to this
 * origin. Anything else is never followed.
 */
export function isSameSitePath(navigateTo: unknown): navigateTo is string {
    if (typeof navigateTo !== 'string' || !navigateTo.startsWith('/') || navigateTo.startsWith('//') || navigateTo.includes('\\')) return false;
    try {
        return new URL(navigateTo, window.location.origin).origin === window.location.origin;
    } catch {
        return false;
    }
}

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
            toast({ description: 'Response deleted' });
            // from a response's own page, back to the list; replace: the deleted response's page is gone from history
            if (isSameSitePath(navigateTo)) router.replace(navigateTo);
            closeModal();
        } else {
            onDeleting?.(false);
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
