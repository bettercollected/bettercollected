'use client';

import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionByUUIDQuery, useGetWorkspaceSubmissionQuery, useRequestWorkspaceSubmissionDeletionByUUIDMutation, useRequestWorkspaceSubmissionDeletionMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { SubmissionProvider } from './SubmissionContext';
import SubmissionLayoutClient from './SubmissionLayoutClient';

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
    const { t } = useTranslation();
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
