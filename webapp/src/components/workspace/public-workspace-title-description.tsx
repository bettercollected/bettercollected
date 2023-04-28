import React, { useState } from 'react';

import { toast } from 'react-toastify';

import ReactContentEditable from '@app/components/inline-editable';
import MarkdownText from '@app/components/ui/markdown-text';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

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

    if (!isFormCreator)
        return (
            <div className={`h-full w-full ${className}`}>
                <div className="w-full md:w-9/12 flex flex-col gap-4">
                    <h4 className="h4">{workspace.title}</h4>
                    <MarkdownText scrollTitle={workspace.title} description={workspace.description} contentStripLength={200} markdownClassName="text-black-700 body3 !not-italic" textClassName="text-black-700 body3 !not-italic" />
                </div>
            </div>
        );
    return (
        <div className={`h-full w-full ${className}`}>
            <div className="w-full md:w-9/12 flex flex-col gap-4">
                <ReactContentEditable callback={handleTitleChange} tag="h4" content={workspace?.title} className="h4" />
                {isMarkdownEditable ? (
                    <ReactContentEditable callback={handleDescriptionChange} tag="p" content={workspace?.description} className="text-black-700 body3 !not-italic" />
                ) : (
                    <MarkdownText
                        scrollTitle={workspace.title}
                        onClick={() => setIsMarkdownEditable(true)}
                        description={workspace.description}
                        contentStripLength={200}
                        markdownClassName="text-black-700 body3 !not-italic"
                        textClassName="text-black-700 body3 !not-italic"
                    />
                )}
            </div>
        </div>
    );
}
