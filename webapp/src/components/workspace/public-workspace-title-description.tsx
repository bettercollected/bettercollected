import React, { useState } from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { toast } from 'react-toastify';

import ReactContentEditable from '@app/components/inline-editable';
import MarkdownText from '@app/components/ui/markdown-text';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IPublicWorkspaceTitleAndDescriptionProps {
    isFormCreator: boolean;
    className?: string;
}

export default function PublicWorkspaceTitleAndDescription({ isFormCreator, className = '' }: IPublicWorkspaceTitleAndDescriptionProps) {
    const [isMarkdownEditable, setIsMarkdownEditable] = useState(false);
    const dispatch = useAppDispatch();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const workspace = useAppSelector((state) => state.workspace);

    const patchWorkspaceInformation = async (formData: any) => {
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast('Something went wrong!!!', { toastId: ToastId.ERROR_TOAST });
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            toast('Workspace Updated!!!', { type: 'default', toastId: ToastId.SUCCESS_TOAST });
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

    if (!isFormCreator)
        return (
            <div className={`h-full w-full ${className}`}>
                <div className="w-full flex flex-col gap-4">
                    <Tooltip title={fullWorkspaceName}>
                        <h4 className="h4">{strippedWorkspaceTitle}</h4>
                    </Tooltip>
                    <MarkdownText scrollTitle={fullWorkspaceName} description={workspace.description} contentStripLength={280} markdownClassName="text-black-700 body3 !leading-none" textClassName="text-black-700 body3 !leading-none" />
                </div>
            </div>
        );
    return (
        <div className={`h-full w-full ${className}`}>
            <div className="w-full flex flex-col gap-4">
                <ReactContentEditable callback={handleTitleChange} tag="h4" content={fullWorkspaceName} className="h4" />
                {isMarkdownEditable ? (
                    <ReactContentEditable callback={handleDescriptionChange} tag="p" content={workspace?.description} className="text-black-700 body3" />
                ) : (
                    <MarkdownText
                        scrollTitle={fullWorkspaceName}
                        onClick={() => setIsMarkdownEditable(true)}
                        description={workspace.description}
                        contentStripLength={280}
                        markdownClassName="text-black-700 body3 !leading-none"
                        textClassName="text-black-700 body3 !leading-none"
                    />
                )}
            </div>
        </div>
    );
}
