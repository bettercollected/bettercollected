import { ChangeEvent, FormEvent, useState } from 'react';

import { useTranslation } from 'next-i18next';

import UploadLogo from '@Components/Common/upload-logo';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useBottomSheetModal } from '@app/components/Modals/Contexts/BottomSheetModalContext';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceInfo({ workspace }: { workspace: WorkspaceDto }) {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const { toast } = useToast();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const { closeBottomSheetModal } = useBottomSheetModal();
    const [workspaceInfo, setWorkspaceInfo] = useState({
        title: workspace.title || '',
        description: workspace.description || '',
        privacy_policy: workspace.privacyPolicy,
        terms_of_service: workspace.termsOfService
    });
    const auth = useAppSelector(selectAuth);

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
            closeBottomSheetModal();
            return;
        }
        Object.keys(workspaceInfo).forEach((key: any) => {
            //@ts-ignore
            if (workspace[key] !== workspaceInfo[key]) formData.append(key, workspaceInfo[key]);
        });
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });

        if (response.error) {
            toast({ description: response.error.data || t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            closeBottomSheetModal();
            toast({ description: t(toastMessage.workspaceUpdate).toString() });
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
            toast({
                description: response.error?.data || t(toastMessage.somethingWentWrong),
                variant: 'destructive'
            });
        }

        if (response.data) {
            dispatch(setWorkspace(response.data));
        }
    };

    return (
        <form onSubmit={onSubmit} className="flex w-full max-w-[540px] flex-col items-start justify-center gap-6 pb-10">
            <div className="relative -top-9 pl-6">
                <UploadLogo onUpload={onProfileImageUpload} logoImageUrl={workspace.profileImage} showRemove={false} dropdownTopPosition={80} />
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">{t('WORKSPACE.SETTINGS.DETAILS.TITLE')}</div>
                <AppInput onChange={onChange} value={workspaceInfo.title} name="title" placeholder={t(placeHolder.workspaceTitle)} />
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">{t('WORKSPACE.SETTINGS.DETAILS.DESCRIPTION')}</div>
                <Textarea
                    className="border-black-300 focus:shadow-input rounded focus:!border-[#B8E8FF] focus:outline-transparent focus:ring-transparent resize-none"
                    rows={3}
                    onChange={onChange}
                    value={workspaceInfo.description}
                    name="description"
                    placeholder={t(placeHolder.description)}
                />
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">Organization&apos;s Privacy Policy URL</div>
                <AppInput onChange={onChange} value={workspaceInfo.privacy_policy} name="privacy_policy" placeholder={'Privacy Policy URL'} />
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">Organization&apos;s Terms of Service URL</div>
                <AppInput onChange={onChange} value={workspaceInfo.terms_of_service} name="terms_of_service" placeholder={'Terms of Service URL'} />
            </div>

            <Button
                data-umami-event="Update Workspace Info From Workspace Settings"
                data-umami-event-email={auth.email}
                className="mt-4 w-full"
                type="submit"
                size="medium"
                variant="secondary"
                disabled={!workspaceInfo.title}
                isLoading={isLoading}
            >
                {t('BUTTON.SAVE_CHANGES')}
            </Button>
        </form>
    );
}
