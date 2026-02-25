import SharedSubmissionLayoutClient from '@app/components/RespondersPortal/_components/SharedSubmissionLayoutClient';
import React from 'react';


export default async function WorkspaceSubmissionLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<{ workspace_name: string, id: string }>
}) {
    const { id } = await params;
    return (
        <SharedSubmissionLayoutClient
            submissionId={id}
            hasCustomDomain={false}
            isUUID={false}
        >
            {children}
        </SharedSubmissionLayoutClient>
    );
}
