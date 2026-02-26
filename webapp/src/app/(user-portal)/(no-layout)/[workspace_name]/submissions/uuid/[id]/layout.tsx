import { getWorkspaceByName } from '@app/lib/server/api';
import SharedSubmissionLayoutClient from '@Components/responder-portal/shared-submission-layout-client';
import { notFound } from 'next/navigation';
import React from 'react';

export default async function WorkspaceSubmissionUUIDLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<{ workspace_name: string, id: string }>
}) {
    const { workspace_name, id } = await params;

    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace?.id) {
        notFound();
    }

    return (
        <SharedSubmissionLayoutClient
            submissionId={id}
            hasCustomDomain={false}
            isUUID={true}
        >
            {children}
        </SharedSubmissionLayoutClient>
    );
}
