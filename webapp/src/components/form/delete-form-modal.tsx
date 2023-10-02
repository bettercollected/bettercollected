import {useTranslation} from 'next-i18next';
import {useRouter} from 'next/router';

import {toast} from 'react-toastify';

import {Close} from '@app/components/icons/close';
import {useModal} from '@app/components/modal-views/context';
import {buttonConstant} from '@app/constants/locales/button';
import {localesCommon} from '@app/constants/locales/common';
import {toastMessage} from '@app/constants/locales/toast-message';
import {useAppSelector} from '@app/store/hooks';
import {useDeleteFormMutation} from '@app/store/workspaces/api';
import AppButton from "@Components/Common/Input/Button/AppButton";
import {ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";

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

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <div className="rounded-[4px] relative m-auto max-w-[500px] items-start justify-between bg-white">
                <div className="relative flex flex-col items-start justify-start p-10">
                    <div>
                        <h4 className="sh1 mb-6">
                            {t(localesCommon.delete)} &quot;{props?.form?.title}&quot;?
                        </h4>
                        <p className="!text-black-600 mb-8 body4 leading-none">{t(localesCommon.deleteMessage)}</p>
                    </div>
                    <div className="flex w-full gap-4 justify-between">
                        <AppButton  variant={ButtonVariant.Danger} data-testid="logout-button" onClick={handleDelete}>
                            {t(buttonConstant.delete)}
                        </AppButton>
                        <AppButton variant={ButtonVariant.Secondary} onClick={() => closeModal()}>
                            {t(buttonConstant.cancel)}
                        </AppButton>
                    </div>
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        </div>
    );
}
