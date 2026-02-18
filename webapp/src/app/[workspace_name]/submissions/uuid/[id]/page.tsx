import React from 'react';
import { notFound } from 'next/navigation';
import environments from '@app/configs/environments';
import SubmissionUUIDWrapper from '@app/app/submissions/uuid/[id]/SubmissionUUIDWrapper';

async function getWorkspaceByName(name: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${name}`, {
            next: { revalidate: 300 }
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching workspace by name:', error);
        return null;
    }
}

export default async function WorkspaceSubmissionUUIDPage({ params }: { params: { workspace_name: string, id: string } }) {
    const { workspace_name, id } = await params;
    
    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace?.id) {
        notFound();
    }

    return <SubmissionUUIDWrapper workspace={workspace} submissionUUID={id} hasCustomDomain={false} />;
}
