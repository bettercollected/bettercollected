import { ChangeEvent, FormEvent, useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import UploadLogo from '@Components/Common/UploadLogo';
import { toast } from 'react-toastify';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceInfo({ workspace }: { workspace: WorkspaceDto }) {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const { closeModal } = useFullScreenModal();
    const [workspaceInfo, setWorkspaceInfo] = useState({
        title: workspace.title || '',
        description: workspace.description || '',
        privacy_policy: workspace.privacyPolicy || environments.PRIVACY_POLICY_URL,
        terms_of_service: workspace.termsOfService || environments.TERMS_OF_SERVICE_URL
    });

    const onChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        if (e.target.name === 'description') {
            if (e.target.value.length >= 280) return;
            setWorkspaceInfo({ ...workspaceInfo, description: e.target.value });
        } else {
            setWorkspaceInfo({ ...workspaceInfo, [e.target.name]: e.target.value });
        }
    };

    const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const formData = new FormData();
        if (workspaceInfo.title === workspace?.title && workspaceInfo.description === workspace?.description && workspaceInfo.privacy_policy === workspace?.privacyPolicy && workspaceInfo.terms_of_service === workspace?.termsOfService) {
            closeModal();
            return;
        }
        Object.keys(workspaceInfo).forEach((key: any) => {
            //@ts-ignore
            if (workspace[key] !== workspaceInfo[key]) formData.append(key, workspaceInfo[key]);
        });
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });

        if (response.error) {
            toast(response.error.data || t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST });
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast(t(toastMessage.workspaceUpdate).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
            closeModal();
        }
    };

    const onProfileImageUpload = async (file: File) => {
        const updateProfileImageFormData = new FormData();
        updateProfileImageFormData.append('profile_image', file);

        const response: any = await patchExistingWorkspace({
            workspace_id: workspace?.id,
            body: updateProfileImageFormData
        });

        if (response.error) {
            toast(response.error?.data || t(toastMessage.somethingWentWrong), {
                toastId: ToastId.ERROR_TOAST,
                type: 'error'
            });
        }

        if (response.data) {
            dispatch(setWorkspace(response.data));
        }
    };

    return (
        <form onSubmit={onSubmit} className="w-full mt-5 flex items-start max-w-[540px] justify-center flex-col gap-6 pb-10">
            <div>
                <UploadLogo onUpload={onProfileImageUpload} logoImageUrl={workspace.profileImage} showRemove={false} />
            </div>
            <div className="gap-2 flex flex-col w-full">
                <div className="body1">{t('WORKSPACE.SETTINGS.DETAILS.TITLE')}</div>
                <AppTextField onChange={onChange} value={workspaceInfo.title} name="title" placeholder={t(placeHolder.workspaceTitle)} />
            </div>
            <div className="gap-2 w-full flex flex-col">
                <div className="body1">{t('WORKSPACE.SETTINGS.DETAILS.DESCRIPTION')}</div>
                <AppTextField multiline fullWidth maxRows={4} minRows={4} onChange={onChange} value={workspaceInfo.description} name="description" placeholder={t(placeHolder.description)} />
            </div>
            <div className="gap-2 w-full flex flex-col">
                <div className="body1">Organization&apos;s Privacy Policy URL</div>
                <AppTextField fullWidth onChange={onChange} value={workspaceInfo.privacy_policy} name="privacy_policy" placeholder={'Privacy Policy URL'} />
            </div>
            <div className="gap-2 w-full flex flex-col">
                <div className="body1">Organization&apos;s Terms of Service URL</div>
                <AppTextField fullWidth onChange={onChange} value={workspaceInfo.terms_of_service} name="terms_of_service" placeholder={'Privacy Policy URL'} />
            </div>

            <div className="flex justify-end mt-4">
                <AppButton type="submit" size={ButtonSize.Medium} variant={ButtonVariant.Secondary} disabled={!workspaceInfo.title} isLoading={isLoading}>
                    {t('BUTTON.SAVE_CHANGES')}
                </AppButton>
            </div>
        </form>
    );
}
