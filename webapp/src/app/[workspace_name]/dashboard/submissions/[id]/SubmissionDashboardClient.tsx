'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import DashboardLayout from '@app/Components/sidebar/dashboard-layout';
import FullScreenLoader from '@app/Components/ui/fullscreen-loader';
import { metaDataTitle } from '@app/constants/locales/meta-data-title';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import Submission from '@Components/RespondersPortal/Submission';
import { toast } from 'react-toastify';
import { useModal } from '@app/Components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useRequestWorkspaceSubmissionDeletionMutation } from '@app/store/workspaces/api';

export default function SubmissionDashboardClient({ submissionId }: { submissionId: string }) {
    const { t } = useTranslation();
    const { id: workspaceId, workspaceName } = useAppSelector(selectWorkspace);
    const { closeModal } = useModal();
    const [requestWorkspaceSubmissionDeletion] = useRequestWorkspaceSubmissionDeletionMutation();

    const { data, isLoading, isError } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspaceId ?? '',
        submission_id: submissionId
    }, {
        skip: !workspaceId || !submissionId
    });

    const handleRequestForDeletion = async () => {
        if (workspaceId && submissionId) {
            try {
                const query = {
                    workspace_id: workspaceId,
                    submission_id: submissionId
                };
                await requestWorkspaceSubmissionDeletion(query);
                toast(t(toastMessage.workspaceSuccess).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
                closeModal();
            } catch (e) {
                toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
            }
        }
    };

    if (isLoading || isError) return <DashboardLayout><FullScreenLoader /></DashboardLayout>;

    return (
        <DashboardLayout>
            <Submission hasCustomDomain={false} data={data} handleRequestForDeletion={handleRequestForDeletion} />
        </DashboardLayout>
    );
}

