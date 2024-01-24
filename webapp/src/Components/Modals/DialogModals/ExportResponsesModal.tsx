import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useAppSelector } from '@app/store/hooks';
import { useLazyExportCSVResponsesQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function ExportResponsesModal({ formId }: { formId: any }) {
    const workspace = useAppSelector(selectWorkspace);
    const [exportCSVTrigger, { isLoading }] = useLazyExportCSVResponsesQuery();

    const { t } = useTranslation();

    const { closeModal } = useModal();

    const handleSubmit = async (event: any) => {
        event.preventDefault();
        const body = {
            workspaceId: workspace.id,
            formId
        };
        const response: any = await exportCSVTrigger(body);
        if (response.data) {
            toast.success(t(toastMessage.csv).toString(), { toastId: ToastId.SUCCESS_TOAST });
        } else if (response.error) {
            toast.error(response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), { toastId: ToastId.ERROR_TOAST });
        }
        closeModal();
    };

    return (
        <HeaderModalWrapper headerTitle="Export Responses as CSV">
            <div className={'flex flex-col gap-2'}>
                <h1 className={'text-black-800 text-base font-medium'}>Export as CSV </h1>
                <h2 className={'body4 !text-black-700'}>Once you export the form responses as CSV. You&apos;ll be receiving the link for the CSV on your email</h2>
                <AppButton className="w-full mt-4" data-testid="save-button" type="submit" onClick={handleSubmit} size={ButtonSize.Medium} variant={ButtonVariant.Primary}>
                    Send me the link
                </AppButton>
            </div>
        </HeaderModalWrapper>
    );
}