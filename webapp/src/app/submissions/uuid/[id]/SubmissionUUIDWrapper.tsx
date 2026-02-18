'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import Submission from '@Components/RespondersPortal/Submission';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useModal } from '@app/Components/modal-views/context';
import FullScreenLoader from '@app/Components/ui/fullscreen-loader';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useGetWorkspaceSubmissionByUUIDQuery, useRequestWorkspaceSubmissionDeletionByUUIDMutation } from '@app/store/workspaces/api';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface ISubmissionUUIDProps {
    workspace: WorkspaceDto;
    submissionUUID: string;
    hasCustomDomain: boolean;
}

export default function SubmissionUUIDWrapper({ workspace, submissionUUID, hasCustomDomain }: ISubmissionUUIDProps) {
    const { toast } = useToast();
    const { t } = useTranslation();
    const { closeModal } = useModal();
    const [requestForDeletionByUUID] = useRequestWorkspaceSubmissionDeletionByUUIDMutation();

    const { data, isLoading } = useGetWorkspaceSubmissionByUUIDQuery({
        workspace_id: workspace?.id ?? '',
        submissionUUID: submissionUUID
    }, {
        skip: !workspace?.id || !submissionUUID
    });

    const handleRequestForDeletion = async () => {
        if (workspace?.id && submissionUUID) {
            try {
                const query = {
                    workspace_id: workspace.id,
                    submission_id: submissionUUID
                };
                await requestForDeletionByUUID(query);
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
