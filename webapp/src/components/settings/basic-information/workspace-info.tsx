import { ChangeEvent, FormEvent, useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import ProfileImageComponent from '@app/components/dashboard/profile-image';
import { useModal } from '@app/components/modal-views/context';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceInfo({ workspace }: any) {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const { closeModal } = useModal();
    const [workspaceInfo, setWorkspaceInfo] = useState({
        title: workspace.title || '',
        description: workspace.description || ''
    });

    const onChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        if (e.target.name === 'title') {
            setWorkspaceInfo({ ...workspaceInfo, title: e.target.value });
        } else if (e.target.name === 'description') {
            setWorkspaceInfo({ ...workspaceInfo, description: e.target.value });
        }
    };

    const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const formData = new FormData();
        if (workspaceInfo.title === workspace?.title && workspaceInfo.description === workspace?.description) {
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

    return (
        <form onSubmit={onSubmit} className="w-full mt-5 flex items-start max-w-[540px] justify-center flex-col gap-6 pb-10">
            <div>
                <ProfileImageComponent workspace={workspace} isFormCreator={true} />
            </div>
            <div className="gap-2 flex flex-col w-full">
                <div className="body1">Organizations Title</div>
                <AppTextField onChange={onChange} value={workspaceInfo.title} name="title" placeholder={t(placeHolder.workspaceTitle)} />
            </div>
            <div className="gap-2 w-full flex flex-col">
                <div className="body1">Organization Descriptions</div>
                <AppTextField multiline onChange={onChange} value={workspaceInfo.description} name="description" placeholder={t(placeHolder.description)} />
            </div>
            <div className="flex justify-end mt-4">
                <AppButton type="submit" size={ButtonSize.Medium} variant={ButtonVariant.Secondary} disabled={isLoading || !workspaceInfo.title} isLoading={isLoading}>
                    {t('BUTTON.SAVE_CHANGES')}
                </AppButton>
            </div>
        </form>
    );
}
