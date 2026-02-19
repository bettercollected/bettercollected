'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useGetWorkspaceSubmissionQuery, useGetWorkspaceSubmissionByUUIDQuery, useRequestWorkspaceSubmissionDeletionMutation, useRequestWorkspaceSubmissionDeletionByUUIDMutation } from '@app/store/workspaces/api';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useModal } from '@app/Components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { SubmissionProvider } from './SubmissionContext';
import SubmissionLayoutClient from './SubmissionLayoutClient';

interface SharedSubmissionLayoutClientProps {
    children: React.ReactNode;
    workspaceId?: string;
    submissionId: string;
    isUUID?: boolean;
    hasCustomDomain?: boolean;
    workspaceName?: string;
}

export default function SharedSubmissionLayoutClient({
    children,
    workspaceId,
    submissionId,
    isUUID = false,
    hasCustomDomain = false,
    workspaceName
}: SharedSubmissionLayoutClientProps) {
    const { toast } = useToast();
    const { t } = useTranslation();
    const { closeModal } = useModal();

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

                if (isUUID) {
                    await requestForDeletionByUUID(query);
                } else {
                    await requestWorkspaceSubmissionDeletion(query);
                }

                toast({ description: t(toastMessage.workspaceSuccess).toString() });
                closeModal();
            } catch (e) {
                toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
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
