import {useState} from 'react';

import {useTranslation} from 'next-i18next';
import AppButton from '@Components/Common/Input/Button/AppButton';
import {ButtonSize, ButtonVariant} from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/HeaderModalWrapper';

import {useModal} from '@app/components/modal-views/context';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {useLazyExportCSVResponsesQuery} from '@app/store/workspaces/api';
import {selectWorkspace, setWorkspace} from '@app/store/workspaces/slice';
import {toast} from "react-toastify";
import {toastMessage} from "@app/constants/locales/toast-message";
import {ToastId} from "@app/constants/toastId";

export default function ExportResponsesModal({formId}: { formId: any }) {
    const workspace = useAppSelector(selectWorkspace);
    const [exportCSVTrigger, {isLoading}] = useLazyExportCSVResponsesQuery();

    const {t} = useTranslation();

    const {closeModal} = useModal();

    const handleSubmit = async (event: any) => {
        event.preventDefault();
        const body = {
            workspaceId: workspace.id,
            formId
        }
        const response: any = await exportCSVTrigger(body);
        if (response.data) {
            toast.success('Exported CSV Successfully', {toastId: ToastId.SUCCESS_TOAST});
        } else if (response.error) {
            toast.error(response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), {toastId: ToastId.ERROR_TOAST});
        }
        closeModal();
    };

    return (
        <HeaderModalWrapper headerTitle="Export Responses">
            <div className={'flex flex-col gap-2'}>
                <h1 className={'body3 !text-black-800 !leading-normal'}> Below are the different options for
                    exporting your responses:
                </h1>
                <AppButton className="w-full mt-4" data-testid="save-button" type="submit"
                           onClick={handleSubmit}
                           size={ButtonSize.Medium} variant={ButtonVariant.Primary}>
                    CSV
                </AppButton>
                <h2 className={'body4 !text-pink-500'}>
                    Note: Once you export the form responses as CSV. You&apos;ll be receiving the link for the CSV on
                    your
                    email
                </h2>
            </div>

        </HeaderModalWrapper>
    );
}
