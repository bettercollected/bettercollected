import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { ToastId } from '@app/constants/toastId';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { checkErrorForWorkspaceName, checkIfPredefinedWorkspaceName } from '@app/utils/workspaceNameUtils';


export default function UpdateWorkspaceHandle() {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const { closeModal } = useModal();
    const { t } = useTranslation();
    const router = useRouter();

    const { openBottomSheetModal } = useBottomSheetModal();

    const workspace = useAppSelector(selectWorkspace);
    const [updateText, setUpdateText] = useState(workspace.workspaceName);

    const [error, setError] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const handleUpdateChange = (event: any) => {
        setUpdateText(event.target.value.toLowerCase());
    };

    useEffect(() => {
        if (checkErrorForWorkspaceName(updateText)) {
            if (!updateText) {
                setErrorMessage(t(onBoarding.fillHandleName));
            } else if (updateText.includes(' ')) {
                setErrorMessage(t(onBoarding.spaceNotAllowed));
            } else if (!updateText.match(/^(?![_-])(?!.*[_-]{2})[a-zA-Z0-9_-]+(?![_-])$/)) {
                setErrorMessage(t(onBoarding.allowedCharacters));
            } else if (checkIfPredefinedWorkspaceName(updateText)) {
                setErrorMessage('It is predefined name. Please use another one.');
            }
            setError(true);
        } else {
            setError(false);
        }
    }, [updateText]);

    const handleSubmit = async (e: any) => {
        e.preventDefault();
        if (error || !updateText) return;
        if (updateText === workspace.workspaceName) {
            closeModal();
            return;
        }
        const formData = new FormData();
        formData.append('workspace_name', updateText);
        const body = {
            workspace_id: workspace.id,
            body: formData
        };
        const response: any = await patchExistingWorkspace(body);
        if (response.data) {
            // dispatch(setWorkspace(response.data));
            toast.info(t(updateWorkspace.handle).toString(), { toastId: ToastId.SUCCESS_TOAST });
            router.replace(`/${response.data.workspaceName}/dashboard`).then(() => {
                openBottomSheetModal('WORKSPACE_SETTINGS', { initialIndex: 1 });
            });
            closeModal();
        } else if (response.error) {
            toast.error(response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), { toastId: ToastId.ERROR_TOAST });
        }
    };
    return (
        <HeaderModalWrapper headerTitle="Update Workspace handle">
            <form className="flex flex-col gap-2" onSubmit={handleSubmit}>
                <div className="h4-new">Enter Slug</div>
                <div className="p2-new text-black-700">Avoid using spaces or special characters. Only “-” and “_” is accepted.</div>
                <div className="p2-new">
                    {environments.HTTP_SCHEME}
                    {environments.CLIENT_DOMAIN}/<span className="p2-new text-pink">{updateText}</span>
                </div>
                <AppTextField value={updateText} onChange={handleUpdateChange} isError={error} error={error} />
                {error && <span className={'text-sm text-red-500 font-normal'}>{errorMessage}</span>}
                <AppButton className="w-full mt-2" disabled={error} data-testid="save-button" type="submit" isLoading={isLoading} size={ButtonSize.Medium} variant={ButtonVariant.Primary}>
                    {t(buttonConstant.updateNow)}
                </AppButton>
            </form>
        </HeaderModalWrapper>
    );
}