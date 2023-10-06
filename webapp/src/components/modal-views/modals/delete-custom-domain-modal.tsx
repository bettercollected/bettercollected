import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceDomainMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function DeleteCustomDomainModal() {
    const { closeModal } = useModal();
    const [deleteWorkspaceDomain, result] = useDeleteWorkspaceDomainMutation();
    const dispatch = useAppDispatch();
    const router = useRouter();

    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);

    const deleteCustomDomain = async (e: any) => {
        e?.preventDefault();
        const res: any = await deleteWorkspaceDomain(workspace.id);
        if (res.data) {
            dispatch(setWorkspace(res.data));
            router.push(router.asPath);
        } else {
            toast.error(t(toastMessage.customDomainDeletionError).toString());
        }
        closeModal();
    };

    return (
        <GenericHalfModal type="danger" headerTitle="Reset Custom Domain" positiveText="Yes" positiveAction={deleteCustomDomain} title={t(updateWorkspace.settings.domain.confirmationTitle)} subTitle={t(updateWorkspace.settings.domain.confirmationDesc)} />
    );
}
