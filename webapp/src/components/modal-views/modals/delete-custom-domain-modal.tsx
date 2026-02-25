import { useTranslation } from 'next-i18next';

import GenericHalfModal from '@Components/Common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceDomainMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';


export default function DeleteCustomDomainModal() {
    const { toast } = useToast();
    const { closeModal } = useModal();
    const [deleteWorkspaceDomain, result] = useDeleteWorkspaceDomainMutation();
    const dispatch = useAppDispatch();

    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);

    const deleteCustomDomain = async (e: any) => {
        e?.preventDefault();
        const res: any = await deleteWorkspaceDomain(workspace.id);
        if (res.data) {
            dispatch(setWorkspace(res.data));
        } else {
            toast({ description: t(toastMessage.customDomainDeletionError).toString(), variant: 'destructive' });
        }
        closeModal();
    };

    return (
        <GenericHalfModal
            loading={result?.isLoading}
            type="danger"
            headerTitle="Reset Custom Domain"
            positiveText="Yes"
            positiveAction={deleteCustomDomain}
            title={t(updateWorkspace.settings.domain.confirmationTitle)}
            subTitle={t(updateWorkspace.settings.domain.confirmationDesc)}
        />
    );
}