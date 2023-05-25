import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/buttons';
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
        e.preventDefault();
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
        <div className="w-full !max-w-[388px] !bg-brand-100 relative bg-white rounded-lg shadow-md p-10  max-w-[502px] sm:max-w-lg md:max-w-xl">
            <Close
                className="absolute cursor-pointer top-5 right-5"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="sh1 mb-4 leading-tight tracking-tight md:text-2xl text-black-900">{t(updateWorkspace.settings.domain.confirmationTitle)}</div>
            <div className="text-black-700 pb-10 ">{t(updateWorkspace.settings.domain.confirmationDesc)}</div>

            <div className="flex w-full gap-4 justify-end">
                <Button data-testid="logout-button" className="flex-1" variant="solid" size="medium" color="danger" onClick={deleteCustomDomain}>
                    {t(buttonConstant.yes)}
                </Button>
                <Button variant="solid" color="gray" size="medium" className="!bg-black-500 flex-1" onClick={() => closeModal()}>
                    {t(buttonConstant.cancel)}
                </Button>
            </div>
        </div>
    );
}
