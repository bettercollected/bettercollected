import React from 'react';
import { notFound } from 'next/navigation';
import ServerSideWorkspaceDispatcher from '@app/Components/HOCs/ServerSideWorkspaceDispatcher';
import { getWorkspaceByName } from '../layout';
import RespondersGroupsClient from './RespondersGroupsClient';

export default async function RespondersGroupsPage({ params }: { params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace) return notFound();

    return (
        <ServerSideWorkspaceDispatcher workspace={workspace}>
            <RespondersGroupsClient />
        </ServerSideWorkspaceDispatcher>
    );
}
