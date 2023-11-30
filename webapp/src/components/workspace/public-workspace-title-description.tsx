import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import MarkdownText from '@Components/Common/Markdown';
import { toast } from 'react-toastify';

import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { toEndDottedStr, trimTooltipTitle } from '@app/utils/stringUtils';

interface IPublicWorkspaceTitleAndDescriptionProps {
    isFormCreator: boolean;
    className?: string;
}

export default function PublicWorkspaceTitleAndDescription({ isFormCreator, className = '' }: IPublicWorkspaceTitleAndDescriptionProps) {
    const [isMarkdownEditable, setIsMarkdownEditable] = useState(false);
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const workspace = useAppSelector((state) => state.workspace);

    const patchWorkspaceInformation = async (formData: any) => {
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast(response.error.data || t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST });
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast(t(toastMessage.workspaceUpdate).toString(), { type: 'default', toastId: ToastId.SUCCESS_TOAST });
        }
    };

    const handleTitleChange = async (sanitizedTitle: string) => {
        const formData = new FormData();
        formData.append('title', sanitizedTitle);

        return await patchWorkspaceInformation(formData);
    };

    const handleDescriptionChange = async (sanitizedDescription: string) => {
        const formData = new FormData();
        formData.append('description', sanitizedDescription);

        setIsMarkdownEditable(false);
        return await patchWorkspaceInformation(formData);
    };

    const fullWorkspaceName = workspace?.title;
    const strippedWorkspaceTitle = toEndDottedStr(fullWorkspaceName, 20);

    return (
        <div className={`h-full w-full ${className}`}>
            <div className="w-full flex flex-col gap-2">
                <Tooltip title={trimTooltipTitle(fullWorkspaceName)}>
                    <h4 className="h5 w-fit">{strippedWorkspaceTitle}</h4>
                </Tooltip>
                <MarkdownText className="lg:max-w-[700px] max-w-[200px] overflow-hidden " markDownClassName={'mt-0 text-sm text-black-600 font-normal'} text={workspace.description} />
            </div>
        </div>
    );
}
