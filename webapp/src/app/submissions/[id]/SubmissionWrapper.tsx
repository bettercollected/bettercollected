'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import Submission from '@Components/RespondersPortal/Submission';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useModal } from '@app/Components/modal-views/context';
import FullScreenLoader from '@app/Components/ui/fullscreen-loader';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceSubmissionQuery, useRequestWorkspaceSubmissionDeletionMutation } from '@app/store/workspaces/api';

interface ISubmissionProps {
    workspace: WorkspaceDto;
    submissionId: string;
    hasCustomDomain: boolean;
}

export default function SubmissionWrapper({ workspace, submissionId, hasCustomDomain }: ISubmissionProps) {
    const { toast } = useToast();
    const { t } = useTranslation();
    const { closeModal } = useModal();
    const [requestWorkspaceSubmissionDeletion] = useRequestWorkspaceSubmissionDeletionMutation();

    const { data, isLoading } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    }, {
        skip: !workspace?.id || !submissionId
    });

    const handleRequestForDeletion = async () => {
        if (workspace?.id && submissionId) {
            try {
                const query = {
                    workspace_id: workspace.id,
                    submission_id: submissionId
                };
                await requestWorkspaceSubmissionDeletion(query);
                toast({ description: t(toastMessage.workspaceSuccess).toString() });
                closeModal();
            } catch (e) {
                toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
            }
        }
    };

    if (isLoading || !data) return <FullScreenLoader />;

    return <Submission hasCustomDomain={hasCustomDomain} data={data} handleRequestForDeletion={handleRequestForDeletion} />;
}
