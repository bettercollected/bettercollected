import { getSubmissionByUuid, getWorkspaceByName } from '@app/lib/server/api';
import { Metadata } from 'next';
import React from 'react';
import SubmissionDashboardLayoutClient from './_components/submission-dashboard-layout-client';

export async function generateMetadata({ params }: { params: Promise<{ workspace_name: string; id: string }> }): Promise<Metadata> {
    const { workspace_name, id } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) {
        return {
            title: 'Workspace Not Found'
        };
    }

    try {
        const submission = await getSubmissionByUuid(workspace.id, id);
        return {
            title: submission?.fileName ? `Submission ${submission.fileName}` : 'Submission Details'
        };
    } catch (e) {
         return {
            title: 'Submission Details'
        };
    }
}

export default async function SubmissionLayout({ children, params }: { children: React.ReactNode; params: Promise<{ id: string }> }) {
    const { id } = await params;
    return (
        <SubmissionDashboardLayoutClient submissionId={id}>
            {children}
        </SubmissionDashboardLayoutClient>
    );
}
