import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/HeaderModalWrapper';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { ToastId } from '@app/constants/toastId';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';

export default function UpdateWorkspaceHandle() {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const { closeModal } = useModal();
    const { t } = useTranslation();
    const { openModal } = useFullScreenModal();
    const router = useRouter();

    const workspace = useAppSelector(selectWorkspace);
    const [updateText, setUpdateText] = useState(workspace.workspaceName);

    const [error, setError] = useState(false);
    const handleUpdateChange = (event: any) => {
        setUpdateText(event.target.value);
    };

    useEffect(() => {
        setError(!updateText.match(/^(?=.*$)(?![_][-])(?!.*[_][-]{2})[a-zA-Z0-9_-]+(?<![_][-])$/));
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
                openModal('WORKSPACE_SETTINGS', { initialIndex: 1 });
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
                <AppButton className="w-full mt-2" disabled={error} data-testid="save-button" type="submit" isLoading={isLoading} size={ButtonSize.Medium} variant={ButtonVariant.Primary}>
                    {t(buttonConstant.updateNow)}
                </AppButton>
            </form>
        </HeaderModalWrapper>
    );
}
