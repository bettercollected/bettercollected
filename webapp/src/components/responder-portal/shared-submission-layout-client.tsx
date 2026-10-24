'use client';

import { useModal } from '@app/components/modal-views/context';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionByUUIDQuery, useGetWorkspaceSubmissionQuery, useRequestWorkspaceSubmissionDeletionByUUIDMutation, useRequestWorkspaceSubmissionDeletionMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import React from 'react';
import { SubmissionProvider } from './submission-context';
import SubmissionLayoutClient from './submission-layout-client';

interface SharedSubmissionLayoutClientProps {
    children: React.ReactNode;
    submissionId: string;
    isUUID?: boolean;
    hasCustomDomain?: boolean;
}

export default function SharedSubmissionLayoutClient({
    children,
    submissionId,
    isUUID = false,
    hasCustomDomain = false,
}: SharedSubmissionLayoutClientProps) {
    const { toast } = useToast();
    // The outcome is told in the respondent's language, like the page.
    const { t } = useRespondentLanguage();
    const { closeModal } = useModal();

    const workspace = useAppSelector(selectWorkspace);
    const workspaceId = workspace?.id;
    const workspaceName = workspace?.workspaceName;

    // Mutations
    const [requestWorkspaceSubmissionDeletion] = useRequestWorkspaceSubmissionDeletionMutation();
    const [requestForDeletionByUUID] = useRequestWorkspaceSubmissionDeletionByUUIDMutation();

    // Queries
    // Use skip to conditionally run only ONE query
    const { data: dataById, isLoading: isLoadingById, isError: isErrorById } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspaceId ?? '',
        submission_id: submissionId
    }, {
        skip: isUUID || !workspaceId || !submissionId
    });

    const { data: dataByUUID, isLoading: isLoadingByUUID, isError: isErrorByUUID } = useGetWorkspaceSubmissionByUUIDQuery({
        workspace_id: workspaceId ?? '',
        submissionUUID: submissionId
    }, {
        skip: !isUUID || !workspaceId || !submissionId
    });

    // Determine active data/state
    const data = isUUID ? dataByUUID : dataById;
    const isLoading = isUUID ? isLoadingByUUID : isLoadingById;
    const isError = isUUID ? isErrorByUUID : isErrorById;

    const handleRequestForDeletion = async () => {
        if (workspaceId && submissionId) {
            try {
                const query = {
                    workspace_id: workspaceId,
                    submission_id: submissionId
                };

                // unwrap(): a failed request throws, so it is never reported as sent.
                if (isUUID) {
                    await requestForDeletionByUUID(query).unwrap();
                } else {
                    await requestWorkspaceSubmissionDeletion(query).unwrap();
                }

                toast({ description: t('SUBMISSION.REQUEST_SENT') });
                closeModal();
            } catch (e) {
                toast({ description: t('SUBMISSION.REQUEST_FAILED'), variant: 'destructive' });
            }
        }
    };

    return (
        <SubmissionProvider value={{ data, isLoading, isError, handleRequestForDeletion, hasCustomDomain, workspaceName }}>
            <SubmissionLayoutClient>
                {children}
            </SubmissionLayoutClient>
        </SubmissionProvider>
    );
}
