import SharedSubmissionLayoutClient from '@app/components/RespondersPortal/_components/SharedSubmissionLayoutClient';
import environments from '@app/configs/environments';
import { notFound } from 'next/navigation';
import React from 'react';

async function getWorkspaceByName(name: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${name}`, {
            cache: 'no-store'
        });
        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace by name:', error);
        return null;
    }
}

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
