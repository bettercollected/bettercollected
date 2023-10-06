import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteFormMutation } from '@app/store/workspaces/api';


export default function DeleteFormModal(props: any) {
    const { closeModal } = useModal();
    const { t } = useTranslation();

    const [trigger] = useDeleteFormMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const router = useRouter();

    const handleDelete = async () => {
        const response: any = await trigger({
            workspaceId: workspace.id,
            formId: props?.form.formId
        }).finally(() => closeModal());
        if (response?.data && !!props?.redirectToDashboard) {
            router.push(`/${workspace.workspaceName}/dashboard`);
            toast(t(toastMessage.formDeleted).toString(), { type: 'success' });
        }
        if (response?.error) {
            toast(t(toastMessage.formDeletionFail).toString(), { type: 'error' });
        }
    };
    return <GenericHalfModal type="danger" positiveText="Delete" positiveAction={handleDelete} headerTitle="Delete Form" title={`Are you sure to delete the form "${props?.form?.title || 'Untitled Form'}"?`} />;
}