import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/navigation';

import GenericHalfModal from '@Components/common/generic-half-modal';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteFormMutation } from '@app/store/workspaces/api';


export default function DeleteFormModal(props: any) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const { toast } = useToast();

    const [trigger] = useDeleteFormMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const router = useRouter();

    const handleDelete = async () => {
        const response: any = await trigger({
            workspaceId: workspace.id,
            formId: props?.form.formId
        }).finally(() => closeModal());
        if (response?.data && !!props?.redirectToDashboard) {
            router.push(`/${workspace.workspaceName}/dashboard/forms`);
            toast({ description: t(toastMessage.formDeleted).toString() });
        }
        if (response?.error) {
            toast({ description: t(toastMessage.formDeletionFail).toString(), variant: 'destructive' });
        }
    };
    return <GenericHalfModal type="danger" positiveText="Delete" positiveAction={handleDelete} headerTitle="Delete Form" title={`Are you sure to delete the form "${props?.form?.title || 'Untitled Form'}"?`} />;
}