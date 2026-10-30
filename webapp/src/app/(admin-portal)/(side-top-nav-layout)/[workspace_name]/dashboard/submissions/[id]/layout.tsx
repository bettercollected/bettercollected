import { getWorkspaceByName } from '@app/lib/server/api';
import { Metadata } from 'next';
import React from 'react';
import SubmissionDashboardLayoutClient from './_components/submission-dashboard-layout-client';

// The id here is a response id, not a receipt number: the title never looks
// the submission up through the public receipt route (rate limited per client
// address, and a lookup from this server would count for every visitor).
export async function generateMetadata({ params }: { params: Promise<{ workspace_name: string; id: string }> }): Promise<Metadata> {
    const { workspace_name } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) {
        return {
            title: 'Workspace Not Found'
        };
    }
    return {
        title: 'Submission Details'
    };
}

export default async function SubmissionLayout({ children, params }: { children: React.ReactNode; params: Promise<{ id: string }> }) {
    const { id } = await params;
    return (
        <SubmissionDashboardLayoutClient submissionId={id}>
            {children}
        </SubmissionDashboardLayoutClient>
    );
}
