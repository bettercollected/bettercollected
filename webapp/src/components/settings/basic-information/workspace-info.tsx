import { ChangeEvent, FormEvent, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/buttons';
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
        }
    };

    return (
        <SettingsCard>
            <form onSubmit={onSubmit}>
                <div>
                    <div className="body1 mb-4">{t(workspaceConstant.title)}</div>
                    <BetterInput onChange={onChange} value={workspaceInfo.title} name="title" placeholder={t(placeHolder.workspaceTitle)} />
                </div>
                <div className="mt-6">
                    <div className="body1 mb-4">{t(workspaceConstant.description)}</div>
                    <BetterInput inputProps={{ maxLength: 280 }} className="w-full" size="medium" rows={5} multiline onChange={onChange} value={workspaceInfo.description} name="description" placeholder={t(placeHolder.description)} />
                </div>
                <div>
                    <Button type="submit" disabled={isLoading || !workspaceInfo.title}>
                        {t(buttonConstant.save)}
                    </Button>
                </div>
            </form>
        </SettingsCard>
    );
}
