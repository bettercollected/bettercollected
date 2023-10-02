import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useDeleteWorkspaceDomainMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import {ButtonSize, ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";
import ModalButton from '@Components/Common/Input/Button/ModalButton';

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
        <div className="w-full   relative bg-white rounded-lg shadow-md p-10  max-w-[502px] sm:max-w-lg md:max-w-xl">
            <Close
                className="absolute cursor-pointer top-5 right-5"
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="sh1 mb-4 leading-tight tracking-tight md:text-2xl text-black-900">{t(updateWorkspace.settings.domain.confirmationTitle)}</div>
            <div className="text-black-700 pb-10 ">{t(updateWorkspace.settings.domain.confirmationDesc)}</div>

            <div className="flex w-full gap-2 justify-end">
                <ModalButton data-testid="logout-button" buttonType={"Modal"} variant={ButtonVariant.Danger} size={ButtonSize.Medium} isLoading={!!result?.isLoading} onClick={deleteCustomDomain}>
                    {t(buttonConstant.yes)}
                </ModalButton>
                <ModalButton variant={ButtonVariant.Secondary} size={ButtonSize.Medium} onClick={() => closeModal()}>
                    {t(buttonConstant.cancel)}
                </ModalButton>
            </div>
        </div>
    );
}
