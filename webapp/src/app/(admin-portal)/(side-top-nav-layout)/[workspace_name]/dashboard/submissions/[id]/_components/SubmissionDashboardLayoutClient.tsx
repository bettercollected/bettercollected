'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import SharedSubmissionLayoutClient from '@Components/RespondersPortal/_components/SharedSubmissionLayoutClient';

interface SubmissionDashboardLayoutClientProps {
    children: React.ReactNode;
    submissionId: string;
}

export default function SubmissionDashboardLayoutClient({ children, submissionId }: SubmissionDashboardLayoutClientProps) {
    const { id: workspaceId } = useAppSelector(selectWorkspace);
    const params = useParams();
    const workspaceName = params?.workspace_name as string;

    return (
        <SharedSubmissionLayoutClient
            workspaceId={workspaceId}
            submissionId={submissionId}
            workspaceName={workspaceName}
            hasCustomDomain={false}
            isUUID={false}
        >
            {children}
        </SharedSubmissionLayoutClient>
    );
}
